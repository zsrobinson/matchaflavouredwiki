"""Cache busting: every reference to a file of the site carries a hash of that file's content."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fingerprint


class FingerprintTests(unittest.TestCase):
    def export(self, files):
        out = Path(tempfile.mkdtemp())
        for name, text in files.items():
            (out / name).parent.mkdir(parents=True, exist_ok=True)
            (out / name).write_text(text)
        fingerprint.apply(str(out))
        return out

    def test_pages_and_stylesheets_reference_versions(self):
        out = self.export({
            'assets/Logo.png': 'logo',
            'images/a/ab/Iron_Ingot.png': 'ingot',
            '_rl/1.css': ':root{--logo:url("/assets/Logo.png")}',
            '_static/site.js': 'js',
            'w/Oven.html': '<link rel="stylesheet" href="/_rl/1.css"><script src="/_static/site.js"></script>'
                           '<img src="/images/a/ab/Iron_Ingot.png" srcset="/images/a/ab/Iron_Ingot.png 1.5x, /assets/Logo.png 2x">'
                           '<div style="background:url(/assets/Logo.png?old)"></div>',
        })
        css = (out / '_rl/1.css').read_text()
        page = (out / 'w/Oven.html').read_text()
        logo, ingot = fingerprint.file_hash(out / 'assets/Logo.png'), fingerprint.file_hash(out / 'images/a/ab/Iron_Ingot.png')
        self.assertEqual(css, ':root{--logo:url("/assets/Logo.png?v=%s")}' % logo)
        self.assertIn('href="/_rl/1.css?v=%s"' % fingerprint.file_hash(out / '_rl/1.css'), page)
        self.assertIn('src="/_static/site.js?v=%s"' % fingerprint.file_hash(out / '_static/site.js'), page)
        self.assertIn('srcset="/images/a/ab/Iron_Ingot.png?v=%s 1.5x, /assets/Logo.png?v=%s 2x"' % (ingot, logo), page)
        self.assertIn('url(/assets/Logo.png?v=%s)' % logo, page)

    def test_a_changed_image_changes_the_stylesheet_that_uses_it(self):
        css = ':root{--logo:url("/assets/Logo.png")}'
        a = self.export({'assets/Logo.png': 'old', '_rl/1.css': css})
        b = self.export({'assets/Logo.png': 'new', '_rl/1.css': css})
        self.assertNotEqual(fingerprint.file_hash(a / '_rl/1.css'), fingerprint.file_hash(b / '_rl/1.css'))

    def test_leaves_text_missing_files_and_other_urls_alone(self):
        page = ('<code>/assets/gui/</code> <a href="/w/Oven">Oven</a> <img src="/images/Missing.png">'
                '<meta content="https://matchaflavou.red/assets/Logo.png">')
        out = self.export({'assets/Logo.png': 'logo', 'w/Oven.html': page})
        self.assertEqual((out / 'w/Oven.html').read_text(), page)

    def test_encoded_names(self):
        out = self.export({"images/1/12/Jack_o'Lantern.png": 'x', 'w/A.html': '<img src="/images/1/12/Jack_o%27Lantern.png">'})
        self.assertIn('?v=', (out / 'w/A.html').read_text())


if __name__ == '__main__':
    unittest.main()
