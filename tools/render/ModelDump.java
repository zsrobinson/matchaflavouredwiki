import java.lang.reflect.Field;
import java.util.*;
import net.minecraft.client.model.geom.LayerDefinitions;
import net.minecraft.client.model.geom.ModelLayerLocation;
import net.minecraft.client.model.geom.PartPose;
import net.minecraft.client.model.geom.builders.*;

// Writes every entity model the game defines (LayerDefinitions.createRoots) as JSON, straight from
// the client's own model code. Run by tools/entity_models.py.
public class ModelDump {
    static Object get(Object o, String name) throws Exception {
        Field f = o.getClass().getDeclaredField(name);
        f.setAccessible(true);
        return f.get(o);
    }
    static String num(float f) {
        if (f == Math.rint(f) && Math.abs(f) < 1e6) return Integer.toString((int) f);
        String s = String.format(Locale.ROOT, "%.5f", f).replaceAll("0+$", "");
        return s.endsWith(".") ? s.substring(0, s.length() - 1) : s;
    }
    static void part(StringBuilder o, PartDefinition p) throws Exception {
        PartPose pose = (PartPose) get(p, "partPose");
        o.append("{");
        List<String> fields = new ArrayList<>();
        float[] pp = {pose.x(), pose.y(), pose.z()};
        if (pp[0] != 0 || pp[1] != 0 || pp[2] != 0) fields.add("\"pivot\":[" + num(pp[0]) + "," + num(pp[1]) + "," + num(pp[2]) + "]");
        if (pose.xRot() != 0 || pose.yRot() != 0 || pose.zRot() != 0) fields.add("\"rot\":[" + num(pose.xRot()) + "," + num(pose.yRot()) + "," + num(pose.zRot()) + "]");
        if (pose.xScale() != 1 || pose.yScale() != 1 || pose.zScale() != 1) fields.add("\"scale\":[" + num(pose.xScale()) + "," + num(pose.yScale()) + "," + num(pose.zScale()) + "]");
        @SuppressWarnings("unchecked") List<CubeDefinition> cubes = (List<CubeDefinition>) get(p, "cubes");
        if (!cubes.isEmpty()) {
            StringBuilder c = new StringBuilder("\"cubes\":[");
            for (int i = 0; i < cubes.size(); i++) {
                CubeDefinition cd = cubes.get(i);
                org.joml.Vector3fc from = (org.joml.Vector3fc) get(cd, "origin"), size = (org.joml.Vector3fc) get(cd, "dimensions");
                UVPair uv = (UVPair) get(cd, "texCoord"), ts = (UVPair) get(cd, "texScale");
                CubeDeformation g = (CubeDeformation) get(cd, "grow");
                @SuppressWarnings("unchecked") Set<Object> faces = (Set<Object>) get(cd, "visibleFaces");
                float gx = (float) get(g, "growX"), gy = (float) get(g, "growY"), gz = (float) get(g, "growZ");
                if (i > 0) c.append(",");
                c.append("{\"uv\":[").append(num(uv.u())).append(",").append(num(uv.v())).append("],\"from\":[")
                    .append(num(from.x())).append(",").append(num(from.y())).append(",").append(num(from.z())).append("],\"size\":[")
                    .append(num(size.x())).append(",").append(num(size.y())).append(",").append(num(size.z())).append("]");
                if (gx != 0 || gy != 0 || gz != 0) c.append(",\"grow\":[").append(num(gx)).append(",").append(num(gy)).append(",").append(num(gz)).append("]");
                if ((boolean) get(cd, "mirror")) c.append(",\"mirror\":true");
                if (ts.u() != 1 || ts.v() != 1) c.append(",\"texScale\":[").append(num(ts.u())).append(",").append(num(ts.v())).append("]");
                if (faces.size() != 6) {
                    List<String> fs = new ArrayList<>();
                    for (Object f : faces) fs.add("\"" + f.toString().toLowerCase(Locale.ROOT) + "\"");
                    Collections.sort(fs);
                    c.append(",\"faces\":[").append(String.join(",", fs)).append("]");
                }
                c.append("}");
            }
            fields.add(c.append("]").toString());
        }
        @SuppressWarnings("unchecked") Map<String, PartDefinition> children = (Map<String, PartDefinition>) get(p, "children");
        if (!children.isEmpty()) {
            StringBuilder c = new StringBuilder("\"children\":{");
            boolean first = true;
            for (String name : new TreeSet<>(children.keySet())) {
                if (!first) c.append(",");
                first = false;
                c.append("\"").append(name).append("\":");
                part(c, children.get(name));
            }
            fields.add(c.append("}").toString());
        }
        o.append(String.join(",", fields)).append("}");
    }
    public static void main(String[] args) throws Exception {
        net.minecraft.SharedConstants.tryDetectVersion();
        net.minecraft.server.Bootstrap.bootStrap();  // some layers (the decorated pot) read registries
        Map<ModelLayerLocation, LayerDefinition> roots = LayerDefinitions.createRoots();
        TreeMap<String, LayerDefinition> sorted = new TreeMap<>();
        for (var e : roots.entrySet()) sorted.put(e.getKey().model() + "#" + e.getKey().layer(), e.getValue());
        StringBuilder o = new StringBuilder("{\n");
        boolean first = true;
        for (var e : sorted.entrySet()) {
            MeshDefinition mesh = (MeshDefinition) get(e.getValue(), "mesh");
            MaterialDefinition mat = (MaterialDefinition) get(e.getValue(), "material");
            if (!first) o.append(",\n");
            first = false;
            o.append("\"").append(e.getKey()).append("\":{\"tex\":[").append(get(mat, "xTexSize")).append(",").append(get(mat, "yTexSize")).append("],\"root\":");
            part(o, mesh.getRoot());
            o.append("}");
        }
        System.out.print(o.append("\n}\n"));
    }
}
