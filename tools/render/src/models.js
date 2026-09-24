// Entity models, in Minecraft's own model coordinates (y points down, the feet are at y=24),
// copied from the game's model classes. A part is placed at `pivot`; each cube is `from` + `size`
// relative to it, with its texture at `uv`. `mirror` flips the texture, as the game does for the
// left limbs of older models that share the right limbs' texture.
//
// To add a mob: reuse one of these models (most undead are humanoid or skeleton) or add one here,
// then add a render to tools/renders.json.

const HEAD = { pivot: [0, 0, 0], cubes: [{ uv: [0, 0], from: [-4, -8, -4], size: [8, 8, 8] }] }
const HAT = { uv: [32, 0], from: [-4, -8, -4], size: [8, 8, 8], inflate: 0.5 }
const BODY = { pivot: [0, 0, 0], cubes: [{ uv: [16, 16], from: [-4, 0, -2], size: [8, 12, 4] }] }
const arm = (side, uv, w = 4, mirror = false) => ({
  pivot: [side * 5, 2, 0],
  cubes: [{ uv, from: [side < 0 ? -w + 1 : -1, -2, -w / 2], size: [w, 12, w], mirror }],
})
const leg = (side, uv, w = 4, mirror = false) => ({
  pivot: [side * (w === 4 ? 1.9 : 2), 12, 0],
  cubes: [{ uv, from: [-w / 2, 0, -w / 2], size: [w, 12, w], mirror }],
})

// HumanoidModel.createMesh: zombies, husks, armor. Left limbs mirror the right ones.
const humanoid = {
  head: { ...HEAD, cubes: [...HEAD.cubes, HAT] },
  body: BODY,
  right_arm: arm(-1, [40, 16]),
  left_arm: arm(1, [40, 16], 4, true),
  right_leg: leg(-1, [0, 16]),
  left_leg: leg(1, [0, 16], 4, true),
}

// Player and drowned: 64x64 textures where the left limbs have their own texture.
const player = {
  ...humanoid,
  left_arm: arm(1, [32, 48]),
  left_leg: leg(1, [16, 48]),
}

// SkeletonModel: thin 2x2 limbs.
const skeleton = {
  ...humanoid,
  right_arm: arm(-1, [40, 16], 2),
  left_arm: arm(1, [40, 16], 2, true),
  right_leg: leg(-1, [0, 16], 2),
  left_leg: leg(1, [0, 16], 2, true),
}

export const MODELS = { humanoid, player, skeleton }

// Poses: rotations in radians per part, in this renderer's space (x < 0 raises a limb forward,
// z < 0 swings the right arm outward), and the camera that shows the pose best (a render's own
// camera wins). Reaching arms need a view from further round the side, or the near arm points
// straight at the camera and looks missing.
export const POSES = {
  stand: { parts: { right_arm: [0, 0, -0.1], left_arm: [0, 0, 0.1] }, camera: { yaw: 35 } },
  reach: { parts: { right_arm: [-1.5, 0, 0], left_arm: [-1.5, 0, 0] }, camera: { yaw: 50 } },  // zombies, husks, drowned
  walk: { parts: { right_arm: [0.35, 0, -0.1], left_arm: [-0.35, 0, 0.1], right_leg: [-0.3, 0, 0], left_leg: [0.3, 0, 0] }, camera: { yaw: 35 } },
}

// Equipment layers (armor): the humanoid model inflated, as HumanoidArmorModel does.
// humanoid = helmet, chestplate, boots; humanoid_leggings = leggings.
export const EQUIPMENT_SLOTS = {
  head: { layer: 'humanoid', parts: ['head'], inflate: 1 },
  chest: { layer: 'humanoid', parts: ['body', 'right_arm', 'left_arm'], inflate: 1 },
  legs: { layer: 'humanoid_leggings', parts: ['body', 'right_leg', 'left_leg'], inflate: 0.5 },
  feet: { layer: 'humanoid', parts: ['right_leg', 'left_leg'], inflate: 1 },
}
