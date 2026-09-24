// Every render is a true isometric view, as minecraft.wiki draws blocks, structures and mobs: seen
// from a corner (yaw 45° plus quarter turns) and looking down at atan(1/√2) ≈ 35.26°, so the three
// visible faces of a cube are the same size and a block's edges run at 30°. A render only picks
// which corner it is seen from.
export const ISO_PITCH = Math.atan(1 / Math.SQRT2) * 180 / Math.PI

export function isoCamera(cam = {}) {
  const extra = Object.keys(cam).filter(k => k !== 'yaw')
  if (extra.length) throw new Error(`camera: only yaw can be set (got ${extra.join(', ')}); renders are isometric`)
  const yaw = cam.yaw ?? 45
  if (((yaw - 45) % 90 + 90) % 90) throw new Error(`camera: yaw must be 45, 135, 225 or 315 (got ${yaw})`)
  return { yaw: yaw * Math.PI / 180, pitch: ISO_PITCH * Math.PI / 180 }
}
