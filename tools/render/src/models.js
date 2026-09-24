// How mobs stand in their renders. The shapes themselves are the game's: entity_models.json is every
// entity model layer of the Minecraft client (LayerDefinitions.createRoots), extracted by
// tools/entity_models.py. What that leaves out is animation: the game's setupAnim moves parts every
// frame, and some models only look right after it (a blaze's rods all sit at the centre until then).
//
// A pose is a function that moves parts, given get(name) -> { pivot: [x, y, z], rot: [x, y, z] }
// (the game's ModelPart x/y/z and xRot/yRot/zRot, in the model's own space: y points down, the
// front faces -z). REST[model] is what setupAnim does to that model on a mob standing still at
// tick 0; a render's named pose from POSES is applied after it. Ported from the 26.2 model classes
// named in each comment.

const PI = Math.PI

// AnimationUtils.bobArms at tick 0: arms held slightly out
const bobArms = get => { get('right_arm').rot[2] += 0.1; get('left_arm').rot[2] -= 0.1 }

// AbstractPiglinModel.setupAnim: ears at 30 degrees, plus the sway at tick 0
const piglinEars = get => { get('left_ear').rot[2] = -PI / 6 - 0.08; get('right_ear').rot[2] = PI / 6 + 0.08 }

export const REST = {
  zombie: bobArms, husk: bobArms, drowned: bobArms, player: bobArms, player_slim: bobArms,
  skeleton: bobArms, stray: bobArms, bogged: bobArms, wither_skeleton: bobArms,
  enderman: bobArms,
  piglin: get => { bobArms(get); piglinEars(get) },
  zombified_piglin: get => { bobArms(get); piglinEars(get) },
  piglin_brute: get => { bobArms(get); piglinEars(get) },
  // BlazeModel.setupAnim: three rings of rods around the body
  blaze: get => {
    const ring = (from, radius, y, start) => {
      for (let i = 0; i < 4; i++) get('part' + (from + i)).pivot = [Math.cos(start + i) * radius, y(from + i), Math.sin(start + i) * radius]
    }
    ring(0, 9, i => -2 + Math.cos(i * 2 * 0.25), 0)
    ring(4, 7, i => 2 + Math.cos(i * 2 * 0.25), PI / 4)
    ring(8, 5, i => 11 + Math.cos(i * 1.5 * 0.5), 0.47123894)
  },
  // WitherBossModel.setupAnim
  wither: get => {
    const rib = (0.065 + 0.05) * PI
    get('ribcage').rot[0] = rib
    get('tail').pivot = [-2, 6.9 + Math.cos(rib) * 10, -0.5 + Math.sin(rib) * 10]
    get('tail').rot[0] = (0.265 + 0.1) * PI
  },
  // PhantomModel.setupAnim, wings at the top of a flap
  phantom: get => {
    const a = 16 * PI / 180
    get('left_wing_base').rot[2] = a; get('left_wing_tip').rot[2] = a
    get('right_wing_base').rot[2] = -a; get('right_wing_tip').rot[2] = -a
    get('tail_base').rot[0] = -10 * PI / 180; get('tail_tip').rot[0] = -10 * PI / 180
  },
  // SilverfishModel.setupAnim: the body's wave
  silverfish: get => {
    const yRot = [], x = []
    for (let i = 0; i < 7; i++) {
      yRot[i] = Math.cos(i * 0.15 * PI) * PI * 0.05 * (1 + Math.abs(i - 2))
      x[i] = Math.sin(i * 0.15 * PI) * PI * 0.2 * Math.abs(i - 2)
      get('segment' + i).rot[1] = yRot[i]; get('segment' + i).pivot[0] = x[i]
    }
    get('layer0').rot[1] = yRot[2]
    get('layer1').rot[1] = yRot[4]; get('layer1').pivot[0] = x[4]
    get('layer2').rot[1] = yRot[1]; get('layer2').pivot[0] = x[1]
  },
  // EnderDragonModel.setupAnim, hovering in place (every past position the same), flapTime 0
  ender_dragon: get => {
    const flap = 0
    get('jaw').rot[0] = (Math.sin(flap) + 1) * 0.2
    let bounce = Math.sin(flap - 1) + 1
    bounce = (bounce * bounce + bounce * 2) * 0.05
    // the root's offset only moves the whole dragon, which the camera fits anyway
    let [x, y, z] = get('neck0').pivot
    for (let i = 0; i < 5; i++) {
      const n = get('neck' + i)
      n.rot = [Math.cos(i * 0.45 + flap) * 0.15, 0, 0]
      n.pivot = [x, y, z]
      x -= Math.sin(n.rot[1]) * Math.cos(n.rot[0]) * 10
      y += Math.sin(n.rot[0]) * 10
      z -= Math.cos(n.rot[1]) * Math.cos(n.rot[0]) * 10
    }
    get('head').pivot = [x, y, z]
    get('head').rot = [0, 0, 0]
    const lw = get('left_wing'), rw = get('right_wing')
    lw.rot = [0.125 - Math.cos(flap) * 0.2, -0.25, -(Math.sin(flap) + 0.125) * 0.8]
    rw.rot = [lw.rot[0], -lw.rot[1], -lw.rot[2]]
    get('left_wing_tip').rot[2] = (Math.sin(flap + 2) + 0.5) * 0.75
    get('right_wing_tip').rot[2] = -get('left_wing_tip').rot[2]
    for (const side of ['left', 'right']) {
      get(side + '_hind_leg').rot[0] = 1 + bounce * 0.1
      get(side + '_hind_leg_tip').rot[0] = 0.5 + bounce * 0.1
      get(side + '_hind_foot').rot[0] = 0.75 + bounce * 0.1
      get(side + '_front_leg').rot[0] = 1.3 + bounce * 0.1
      get(side + '_front_leg_tip').rot[0] = -0.5 - bounce * 0.1
      get(side + '_front_foot').rot[0] = 0.75 + bounce * 0.1
    }
    ;[x, y, z] = get('tail0').pivot
    let tailX = 0
    for (let i = 0; i < 12; i++) {
      const t = get('tail' + i)
      tailX += Math.sin(i * 0.45 + flap) * 0.05
      t.rot = [tailX, PI, 0]
      t.pivot = [x, y, z]
      y += Math.sin(t.rot[0]) * 10
      z -= Math.cos(t.rot[1]) * Math.cos(t.rot[0]) * 10
      x -= Math.sin(t.rot[1]) * Math.cos(t.rot[0]) * 10
    }
  },
}

// Named poses a render can ask for, applied after REST.
export const POSES = {
  // AnimationUtils.animateZombieArms, not aggressive, at tick 0: arms raised, bobbed twice
  zombie_arms: get => {
    const r = get('right_arm'), l = get('left_arm')
    r.rot = [-PI / 2.25, -0.1, 0.2]
    l.rot = [-PI / 2.25, 0.1, -0.2]
  },
}

// The camera each model is seen from best, when a render doesn't give one. Raised arms need a view
// from further round the side, or the near arm points straight at the camera and looks missing.
export const CAMERAS = {
  zombie_arms: { yaw: 50 },
  ender_dragon: { yaw: 145, pitch: 25 },
  phantom: { yaw: 35, pitch: 35 },
  spider: { yaw: 35, pitch: 25 },
  cave_spider: { yaw: 35, pitch: 25 },
  silverfish: { yaw: 35, pitch: 30 },
}

// Armor: the equipment asset's layer for each slot, and the armor model layer the game draws it on
// (HumanoidModel.createArmorMeshSet: <model>#helmet, #chestplate, #leggings, #boots).
export const EQUIPMENT_SLOTS = {
  head: { layer: 'humanoid', model: 'helmet' },
  chest: { layer: 'humanoid', model: 'chestplate' },
  legs: { layer: 'humanoid_leggings', model: 'leggings' },
  feet: { layer: 'humanoid', model: 'boots' },
}
