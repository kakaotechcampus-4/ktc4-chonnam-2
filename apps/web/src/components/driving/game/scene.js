import * as THREE from 'three'
import { courseBetween, LANES } from './rules.mjs'
import { motion } from './motion.mjs'
const GRID = 96
const signalAspect = () => ({
  red: false,
  yellow: false,
  left: true,
  straight: true,
})
const pedestrianAspect = () => ({ phase: 'red', elapsed: 0 })
export function createView(canvas) {
  let renderer, scene
  const ownedRoots = []
  scene = new THREE.Scene()
  ownedRoots.push(scene)
  scene.background = new THREE.Color('#c0e1f0')
  scene.fog = new THREE.Fog('#c0e1f0', 45, 112)
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.18
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  const camera = new THREE.PerspectiveCamera(53, 1.6, 0.05, 220)
  scene.add(camera)
  scene.add(new THREE.HemisphereLight('#e2f0ff', '#c1bda1', 2.8))
  const sun = new THREE.DirectionalLight('#fff0d3', 2.1)
  sun.castShadow = true
  sun.shadow.mapSize.set(1024, 1024)
  Object.assign(sun.shadow.camera, {
    left: -38,
    right: 38,
    top: 38,
    bottom: -38,
    near: 1,
    far: 120,
  })
  sun.shadow.normalBias = 0.05
  sun.shadow.bias = -0.00015
  scene.add(sun, sun.target)
  const fill = new THREE.DirectionalLight('#d4e8ff', 0.6)
  fill.position.set(25, 8, 1)
  scene.add(fill)
  const mats = new Map(),
    geos = new Map()
  function mat(color, roughness = 0.78, metalness = 0) {
    const k = [color, roughness, metalness].join(':')
    if (!mats.has(k))
      mats.set(
        k,
        new THREE.MeshStandardMaterial({ color, roughness, metalness }),
      )
    return mats.get(k)
  }
  function rounded(w, h, d, r) {
    const k = [w, h, d, r].join(':')
    if (geos.has(k)) return geos.get(k)
    const g = new THREE.BoxGeometry(w, h, d, r ? 4 : 1, r ? 4 : 1, r ? 4 : 1)
    if (r) {
      const p = g.attributes.position,
        v = new THREE.Vector3(),
        q = new THREE.Vector3(),
        a = new THREE.Vector3(w / 2 - r, h / 2 - r, d / 2 - r)
      for (let i = 0; i < p.count; i++) {
        v.fromBufferAttribute(p, i)
        q.set(
          Math.max(-a.x, Math.min(a.x, v.x)),
          Math.max(-a.y, Math.min(a.y, v.y)),
          Math.max(-a.z, Math.min(a.z, v.z)),
        )
        v.sub(q).normalize().multiplyScalar(r).add(q)
        p.setXYZ(i, v.x, v.y, v.z)
      }
      g.computeVertexNormals()
    }
    geos.set(k, g)
    return g
  }
  const M = {
    road: mat('#78838a'),
    grass: mat('#93b57e'),
    sidewalk: mat('#e2dbca'),
    curb: mat('#eeece2'),
    line: mat('#f3efdf'),
    center: mat('#e2cf8d'),
    trunk: mat('#8b7961'),
    leaf: [mat('#65a282'), mat('#7db58b'), mat('#a0bc7b')],
    ivory: mat('#eee2cb'),
    peach: mat('#e0b9a4'),
    blue: mat('#a9ced6'),
    glass: mat('#809fab', 0.24, 0.2),
    silver: mat('#b9c7cd', 0.3, 0.65),
    dark: mat('#3b4852', 0.55),
    white: mat('#f0eee5'),
  }
  const textureCanvas = document.createElement('canvas')
  textureCanvas.width = textureCanvas.height = 128
  const textureCtx = textureCanvas.getContext('2d'),
    pixels = textureCtx.createImageData(128, 128)
  let seed = 17
  for (let i = 0; i < pixels.data.length; i += 4) {
    seed = (seed * 16807) % 2147483647
    const n = 128 + (seed % 21) - 10
    pixels.data[i] = pixels.data[i + 1] = pixels.data[i + 2] = n
    pixels.data[i + 3] = 255
  }
  textureCtx.putImageData(pixels, 0, 0)
  const grain = new THREE.CanvasTexture(textureCanvas)
  grain.wrapS = grain.wrapT = THREE.RepeatWrapping
  grain.colorSpace = THREE.SRGBColorSpace
  M.road.map = grain
  M.road.color.set('#adb8c0')
  const sphere = new THREE.SphereGeometry(1, 18, 12),
    trunkGeo = new THREE.CylinderGeometry(0.12, 0.14, 2.7, 10)
  function mesh(geo, m, x, y, z, p) {
    const o = new THREE.Mesh(geo, m)
    o.position.set(x, y, z)
    o.castShadow = true
    o.receiveShadow = true
    p.add(o)
    return o
  }
  function box(w, h, d, m, x, y, z, p, r = 0) {
    return mesh(rounded(w, h, d, r), m, x, y, z, p)
  }
  function oval(xr, yr, zr, m, x, y, z, p) {
    const o = mesh(sphere, m, x, y, z, p)
    o.scale.set(xr, yr, zr)
    return o
  }
  function tree(x, z, v, p) {
    const g = new THREE.Group()
    g.position.set(x, 0, z)
    p.add(g)
    mesh(trunkGeo, M.trunk, 0, 1.35, 0, g)
    const h = 3.8 + v * 0.26
    oval(0.93, 1.03, 0.98, M.leaf[v % 3], 0.05, h - 0.15, 0, g)
    oval(0.83, 0.9, 0.84, M.leaf[(v + 1) % 3], -0.63, h - 0.52, 0.12, g)
    oval(0.81, 0.84, 0.81, M.leaf[v % 3], 0.64, h - 0.43, -0.09, g)
    oval(0.85, 0.7, 0.82, M.leaf[v % 3], -0.13, h - 0.87, 0.2, g)
  }
  function building(x, z, v, rot, p) {
    const g = new THREE.Group()
    g.position.set(x, 0, z)
    g.rotation.y = rot
    p.add(g)
    const ht = [5, 7, 5.8][v % 3],
      w = 6.7,
      d = 7
    box(w, ht, d, [M.ivory, M.peach, M.blue][v % 3], 0, ht / 2, 0, g, 0.18)
    box(w + 0.25, 0.22, d + 0.23, M.white, 0, ht + 0.02, 0, g, 0.06)
    for (let y = 1.6; y < ht - 1; y += 1.6) {
      for (let a = -2; a <= 2; a += 2) {
        box(0.95, 1, 0.025, M.glass, a, y, 3.52, g)
        box(0.025, 1, 1.05, M.glass, 3.36, y, a, g)
        box(1.1, 0.09, 0.14, M.white, a, y - 0.55, 3.56, g)
      }
    }
    box(3.8, 0.14, 0.8, mat('#839f9c'), 0, 2.3, 3.7, g, 0.045)
  }
  const tile = new THREE.Group()
  ownedRoots.push(tile)
  const signalMaterial = new THREE.MeshBasicMaterial({
    color: '#ffffff',
    toneMapped: false,
  })
  const signalColor = new THREE.Color(),
    signalColors = ['#fb715f', '#ffcc52', '#7ae4a1', '#7ae4a1']
  function updateSignals(time) {
    for (const b of signalBatches) {
      let n = 0
      for (let ix = 0; ix <= 0; ix++)
        for (let iz = -1; iz <= 1; iz++) {
          const x = (gridX + ix) * GRID,
            z = (gridZ + iz) * GRID
          for (const s of b.signals) {
            const a = signalAspect(s.axis, time, x, z)
            let on, color
            if (s.kind === 'ped') {
              const p = pedestrianAspect(s.axis, time, x, z)
              on =
                s.index === 0
                  ? p.phase === 'red'
                  : p.phase === 'walk' ||
                    (p.phase === 'flash' && Math.floor(p.elapsed * 2) % 2 === 0)
              color = s.index === 0 ? signalColors[0] : signalColors[3]
            } else {
              on = [a.red, a.yellow, a.left, a.straight][s.index]
              color = signalColors[s.index]
            }
            b.mesh.setColorAt(n++, signalColor.set(on ? color : '#263a3c'))
          }
        }
      b.mesh.instanceColor.needsUpdate = true
    }
  }
  function litPart(o, axis, index, kind = 'vehicle') {
    o.userData.signal = { axis, index, kind }
    o.castShadow = false
    return o
  }
  function pedestrianSignal(x, z, axis, p) {
    const g = new THREE.Group()
    g.position.set(x, 0, z)
    g.rotation.y = x > 0 ? -Math.PI / 2 : Math.PI / 2
    p.add(g)
    mesh(
      new THREE.CylinderGeometry(0.055, 0.075, 2.7, 8),
      M.dark,
      0,
      1.35,
      0,
      g,
    )
    box(0.53, 1.12, 0.25, M.dark, 0, 2.65, 0, g, 0.07)
    for (const i of [0, 1]) {
      const y = 2.91 - i * 0.52
      box(0.4, 0.44, 0.018, mat('#233338'), 0, y, 0.135, g, 0.04)
      litPart(
        oval(0.046, 0.046, 0.019, signalMaterial, 0, y + 0.13, 0.157, g),
        axis,
        i,
        'ped',
      )
      litPart(
        box(0.065, 0.16, 0.018, signalMaterial, 0, y + 0.01, 0.158, g),
        axis,
        i,
        'ped',
      )
      for (const side of [-1, 1]) {
        const arm = litPart(
          box(
            0.035,
            0.14,
            0.018,
            signalMaterial,
            side * 0.07,
            y + 0.025,
            0.158,
            g,
          ),
          axis,
          i,
          'ped',
        )
        arm.rotation.z = i ? side * 0.7 : side * 0.12
        const leg = litPart(
          box(
            0.04,
            0.15,
            0.018,
            signalMaterial,
            side * (i ? 0.059 : 0.029),
            y - 0.13,
            0.158,
            g,
          ),
          axis,
          i,
          'ped',
        )
        leg.rotation.z = i ? side * 0.5 : 0
      }
    }
  }
  box(14, 0.1, 96, M.road, 0, -0.04, 0, tile)
  box(96, 0.1, 14, M.road, 0, -0.041, 0, tile)
  box(19, 0.09, 19, M.road, 0, -0.02, 0, tile)
  for (const sx of [-1, 1])
    for (const sz of [-1, 1]) {
      box(38.8, 0.18, 38.8, M.sidewalk, sx * 28.6, 0.02, sz * 28.6, tile, 0.25)
      box(33, 0.07, 33, M.grass, sx * 31, 0.14, sz * 31, tile, 0.04)
    }
  for (let arm = 0; arm < 4; arm++) {
    const a = new THREE.Group()
    a.rotation.y = (arm * Math.PI) / 2
    tile.add(a)
    for (const x of [-8.05, 8.05]) {
      box(2.1, 0.1, 38.8, M.road, x, -0.04, -28.6, a)
      box(0.09, 0.015, 32, M.line, x + Math.sign(x) * 0.87, 0.024, -31, a)
      for (const z of [-16, -28, -40, -47])
        box(1.9, 0.018, 0.09, M.line, x, 0.024, z, a)
    }
    for (const x of [-7.0, 7.0])
      box(0.11, 0.018, 37, M.line, x, 0.023, -29.5, a)
    for (const x of [-5.84, -5.66])
      box(0.08, 0.018, 36, M.center, x, 0.025, -30, a)
    for (const x of [-1.75, 1.75]) {
      box(0.11, 0.02, 10, M.line, x, 0.025, -19, a)
      for (let z = -27; z >= -47; z -= 6)
        box(0.11, 0.02, 2.7, M.line, x, 0.025, z, a)
    }
    for (const x of [-9.2, 9.2])
      box(0.22, 0.18, 35, M.curb, x, 0.13, -30.5, a, 0.07)
    for (let j = 0; j < 3; j++) {
      for (const sx of [-1, 1]) {
        tree(sx * 10.3, -19 - j * 12, (j + arm) % 3, a)
        box(
          1.5,
          0.05,
          1.5,
          mat('#a5b390'),
          sx * 10.3,
          0.14,
          -19 - j * 12,
          a,
          0.02,
        )
      }
    }
    for (let j = 0; j < 3; j++)
      building(-17, -23 - j * 10.5, (arm + j) % 3, Math.PI / 2, a)
    building(17, -31, (arm + 1) % 3, -Math.PI / 2, a)
    oval(0.8, 0.7, 2.1, mat('#83a27a'), 17, 0.8, -42, a)
    // Shoulder, stop line and raised pavement stay outside the vehicle's turning arc.
    for (let x = -6; x <= 6; x += 1.2)
      box(0.63, 0.015, 2, M.line, x, 0.027, -10.5, a)
    box(6.6, 0.018, 0.28, M.line, -3.5, 0.03, -14, a)
    // Far-side signals remain visible from the driver's eye at the stop line.
    mesh(
      new THREE.CylinderGeometry(0.085, 0.12, 7.9, 10),
      M.dark,
      -10.2,
      4.1,
      12,
      a,
    )
    box(7, 0.14, 0.14, M.dark, -6.85, 8, 12, a, 0.04)
    box(3.08, 0.78, 0.34, M.dark, -3.5, 7.75, 12, a, 0.1)
    for (let i = 0; i < 4; i++) {
      const x = -2.39 - i * 0.74
      if (i === 2) {
        oval(0.24, 0.24, 0.06, mat('#263a3c'), x, 7.75, 11.79, a)
        litPart(
          box(0.3, 0.065, 0.018, signalMaterial, x, 7.75, 11.72, a),
          arm % 2,
          i,
        )
        for (const s of [-1, 1]) {
          const part = litPart(
            box(
              0.17,
              0.065,
              0.018,
              signalMaterial,
              x + 0.1,
              7.75 + s * 0.057,
              11.72,
              a,
            ),
            arm % 2,
            i,
          )
          part.rotation.z = (-s * Math.PI) / 4
        }
      } else
        litPart(
          oval(0.24, 0.24, 0.06, signalMaterial, x, 7.75, 11.79, a),
          arm % 2,
          i,
        )
    }
    for (const side of [-1, 1]) pedestrianSignal(side * 9.85, -10.5, arm % 2, a)
    // A bench and small flowers make the pavement feel inhabited.
    box(0.65, 0.14, 2, mat('#b28c6b'), 12.9, 0.64, -35, a, 0.05)
    box(0.12, 0.55, 2, mat('#b28c6b'), 13.17, 0.99, -35, a, 0.035)
    for (const z of [-35.7, -34.3])
      box(0.45, 0.49, 0.1, M.dark, 12.9, 0.37, z, a, 0.02)
    for (let j = 0; j < 4; j++) {
      mesh(
        new THREE.CylinderGeometry(0.16, 0.13, 0.28, 8),
        mat('#cfaa8a'),
        13,
        0.3,
        -22 - j * 0.45,
        a,
      )
      oval(
        0.21,
        0.15,
        0.2,
        mat(j % 2 ? '#edcd83' : '#d5a29e'),
        13,
        0.57,
        -22 - j * 0.45,
        a,
      )
    }
  }
  // Batch repeated scenery by geometry/material; camera movement does not rebuild the scene.
  tile.updateMatrixWorld(true)
  const batches = new Map()
  tile.traverse((o) => {
    if (!o.isMesh) return
    const key = o.geometry.uuid + o.material.uuid
    if (!batches.has(key))
      batches.set(key, {
        geo: o.geometry,
        mat: o.material,
        transforms: [],
        signals: [],
      })
    const b = batches.get(key)
    b.transforms.push(o.matrixWorld.clone())
    if (o.userData.signal) b.signals.push(o.userData.signal)
  })
  const signalBatches = [...batches.values()].filter(
    (b) => b.mat === signalMaterial,
  )
  for (const b of batches.values())
    if (b.mat === M.road) {
      const pos = b.geo.attributes.position,
        uv = b.geo.attributes.uv
      for (let i = 0; i < pos.count; i++)
        uv.setXY(i, pos.getX(i) / 4, pos.getZ(i) / 4)
      uv.needsUpdate = true
    }
  for (const b of batches.values()) {
    b.mesh = new THREE.InstancedMesh(b.geo, b.mat, b.transforms.length * 3)
    b.mesh.castShadow = true
    b.mesh.receiveShadow = true
    b.mesh.frustumCulled = false
    scene.add(b.mesh)
  }
  const ground = box(800, 0.1, 800, M.grass, 0, -0.17, 0, scene)
  ground.castShadow = false
  let gridX = 9999,
    gridZ = 9999
  const trans = new THREE.Matrix4(),
    out = new THREE.Matrix4()
  function placeWorld(x, z) {
    const gx = Math.round(x / GRID),
      gz = Math.round(z / GRID)
    if (gx === gridX && gz === gridZ) return
    gridX = gx
    gridZ = gz
    for (const b of batches.values()) {
      let n = 0
      for (let ix = 0; ix <= 0; ix++)
        for (let iz = -1; iz <= 1; iz++) {
          trans.makeTranslation((gx + ix) * GRID, 0, (gz + iz) * GRID)
          for (const original of b.transforms) {
            out.multiplyMatrices(trans, original)
            b.mesh.setMatrixAt(n++, out)
          }
        }
      b.mesh.instanceMatrix.needsUpdate = true
    }
    ground.position.set(gx * GRID, -0.17, gz * GRID)
  }
  const clouds = new THREE.Group()
  scene.add(clouds)
  for (let k = 0; k < 5; k++) {
    const angle = (k * Math.PI * 2) / 5
    for (let j = 0; j < 3; j++) {
      const c = oval(
        5,
        1.6 + (j % 2) * 0.7,
        2.8,
        mat('#f9f8ee'),
        Math.cos(angle) * 100 + j * 4,
        24 + (k % 2) * 5,
        Math.sin(angle) * 100,
        clouds,
      )
      c.castShadow = false
      c.receiveShadow = false
    }
  }
  const carPaints = ['#93b7a7', '#d6c4a6', '#8ba8bd', '#c69e8c'],
    tireGeo = new THREE.CylinderGeometry(0.32, 0.32, 0.19, 16),
    hubGeo = new THREE.CylinderGeometry(0.16, 0.16, 0.205, 12),
    tailMaterial = new THREE.MeshBasicMaterial({
      color: '#dc8273',
      toneMapped: false,
    })
  function makeTrafficCar(index, truck = false, player = false) {
    const g = new THREE.Group(),
      paint = mat(player ? '#f0eee5' : carPaints[index % 4], 0.4, 0.08),
      glass = mat('#617c88', 0.3, 0.15),
      tires = mat('#354049'),
      rims = mat('#b1c0c3', 0.4, 0.35),
      wheels = []
    box(1.82, 0.51, 4.05, paint, 0, 0.66, 0, g, 0.2)
    box(1.69, 0.16, 3.8, paint, 0, 0.94, -0.05, g, 0.07)
    box(1.48, 0.58, 2.13, glass, 0, 1.22, 0.17, g, 0.16)
    box(1.43, 0.12, 1.69, paint, 0, 1.51, 0.2, g, 0.05)
    for (const x of [-0.73, 0.73]) {
      box(0.065, 0.54, 0.12, paint, x, 1.23, 0.16, g, 0.02)
      box(0.065, 0.46, 0.12, paint, x, 1.22, 0.91, g, 0.02)
      box(0.23, 0.1, 0.25, paint, x * 1.22, 1.1, -0.71, g, 0.045)
    }
    box(0.88, 0.14, 0.035, M.dark, 0, 0.57, -2.025, g, 0.025)
    box(0.34, 0.12, 0.04, M.white, 0, 0.58, 2.03, g, 0.015)
    for (const s of [-1, 1]) {
      box(0.39, 0.14, 0.05, mat('#f0e6bc'), s * 0.59, 0.78, -2.025, g, 0.045)
      const tail = box(
        0.39,
        0.13,
        0.05,
        tailMaterial,
        s * 0.59,
        0.8,
        2.03,
        g,
        0.035,
      )
      tail.userData.brake = true
    }
    for (const x of [-0.84, 0.84])
      for (const z of [-1.24, 1.26]) {
        const wheel = new THREE.Group()
        wheel.position.set(x, 0.36, z)
        g.add(wheel)
        mesh(tireGeo, tires, 0, 0, 0, wheel).rotation.z = Math.PI / 2
        mesh(hubGeo, rims, 0, 0, 0, wheel).rotation.z = Math.PI / 2
        wheels.push(wheel)
      }

    if (truck) {
      box(1.93, 2.05, 3.3, mat('#c5cbbf'), 0, 2.05, 0.28, g, 0.1)
      box(1.99, 0.12, 3.39, M.white, 0, 3.1, 0.28, g, 0.035)
      box(1.82, 1.83, 0.035, mat('#b4beb7'), 0, 2.05, 1.96, g, 0.04)
      for (const x of [-0.54, 0.54])
        box(0.045, 1.6, 0.035, M.silver, x, 2.05, 1.99, g, 0.01)
    }
    return { g, wheels }
  }
  const templates = new Map()
  const player = makeTrafficCar(0, false, true)
  scene.add(player.g)
  player.body = new THREE.Group()
  for (const child of [...player.g.children])
    if (!player.wheels.includes(child)) player.body.add(child)
  player.g.add(player.body)
  const jets = new THREE.Group(),
    jetMaterial = new THREE.MeshBasicMaterial({
      color: '#eef3ee',
      transparent: true,
      opacity: 0.48,
      depthWrite: false,
    }),
    jetGeometry = new THREE.ConeGeometry(0.15, 0.85, 8, 1, true)
  for (const x of [-0.65, 0.65])
    for (const z of [-1.1, 1.1]) {
      const jet = new THREE.Mesh(jetGeometry, jetMaterial)
      jet.position.set(x, -0.22, z)
      jets.add(jet)
    }
  player.g.add(jets)
  // Roll around the vehicle's center, not around its contact point on the road.
  player.stunt = new THREE.Group()
  player.stunt.position.y = 0.8
  const stuntModel = new THREE.Group()
  stuntModel.position.y = -0.8
  for (const child of [...player.g.children]) stuntModel.add(child)
  player.stunt.add(stuntModel)
  player.g.add(player.stunt)
  const contactCanvas = document.createElement('canvas')
  contactCanvas.width = contactCanvas.height = 64
  const contactContext = contactCanvas.getContext('2d'),
    gradient = contactContext.createRadialGradient(32, 32, 6, 32, 32, 32)
  gradient.addColorStop(0, '#253b4d99')
  gradient.addColorStop(1, '#253b4d00')
  contactContext.fillStyle = gradient
  contactContext.fillRect(0, 0, 64, 64)
  const contact = new THREE.Mesh(
    new THREE.PlaneGeometry(3, 5.6),
    new THREE.MeshBasicMaterial({
      map: new THREE.CanvasTexture(contactCanvas),
      transparent: true,
      depthWrite: false,
      opacity: 0.7,
    }),
  )
  contact.rotation.x = -Math.PI / 2
  scene.add(contact)
  // Reuse geometry and materials across traffic instances.
  const carBatches = new Map(),
    dummy = new THREE.Matrix4(),
    origin = new THREE.Matrix4()
  for (let type = 0; type < 2; type++)
    for (let color = 0; color < 4; color++) {
      const template = makeTrafficCar(color, type === 1)
      template.g.updateMatrixWorld(true)
      const parts = []
      template.g.traverse((o) => {
        if (!o.isMesh) return
        const key = o.geometry.uuid + o.material.uuid
        if (!carBatches.has(key))
          carBatches.set(key, {
            geo: o.geometry,
            mat: o.material,
            parts: [],
            mesh: null,
          })
        parts.push({ key, matrix: o.matrixWorld.clone() })
      })
      templates.set(`${type}:${color}`, parts)
      ownedRoots.push(template.g)
    }
  for (const b of carBatches.values()) {
    b.mesh = new THREE.InstancedMesh(b.geo, b.mat, 256)
    b.mesh.castShadow = true
    b.mesh.receiveShadow = true
    b.mesh.frustumCulled = false
    b.mesh.count = 0
    scene.add(b.mesh)
  }
  const coinPose = new THREE.Object3D(),
    coinBatches = []
  function coinBatch(geometry, material) {
    const mesh = new THREE.InstancedMesh(geometry, material, 32)
    mesh.frustumCulled = false
    mesh.count = 0
    scene.add(mesh)
    coinBatches.push(mesh)
    return mesh
  }
  coinBatch(
    new THREE.CylinderGeometry(0.43, 0.43, 0.11, 24).rotateX(Math.PI / 2),
    new THREE.MeshStandardMaterial({
      color: '#d8b064',
      metalness: 0.3,
      roughness: 0.42,
    }),
  )
  coinBatch(
    new THREE.TorusGeometry(0.32, 0.026, 6, 24).translate(0, 0, 0.065),
    new THREE.MeshBasicMaterial({ color: '#fff0bd' }),
  )
  coinBatch(
    new THREE.BoxGeometry(0.055, 0.3, 0.025).translate(0, 0, 0.065),
    new THREE.MeshBasicMaterial({ color: '#fff0bd' }),
  )
  const glints = new THREE.InstancedMesh(
    new THREE.OctahedronGeometry(0.08),
    new THREE.MeshBasicMaterial({
      color: '#fff1be',
      transparent: true,
      opacity: 0,
      depthWrite: false,
    }),
    5,
  )
  glints.frustumCulled = false
  scene.add(glints)
  const shield = new THREE.Mesh(
    new THREE.SphereGeometry(1, 24, 16),
    new THREE.MeshBasicMaterial({
      color: '#b4d9bf',
      transparent: true,
      opacity: 0.1,
      depthWrite: false,
    }),
  )
  scene.add(shield)
  // A protected obstacle becomes translucent while the car passes it, without a crash animation.
  const ghostCars = new Map()
  function ghostCar(c) {
    let ghost = ghostCars.get(c.id)
    if (!ghost) {
      ghost = makeTrafficCar(c.color, c.type === 'truck').g
      ghost.traverse((o) => {
        if (o.isMesh) {
          o.material = o.material.clone()
          o.material.transparent = true
          o.material.opacity = 0.2
          o.material.depthWrite = false
          o.castShadow = false
        }
      })
      scene.add(ghost)
      ghostCars.set(c.id, ghost)
    }
    return ghost
  }
  function removeGhost(id, ghost) {
    scene.remove(ghost)
    ghost.traverse((o) => {
      if (o.isMesh) o.material.dispose()
    })
    ghostCars.delete(id)
  }
  const roadObjects = new Map()
  function roadObject(c) {
    let g = roadObjects.get(c.id)
    if (g) return g
    g = new THREE.Group()
    if (c.type === 'gate') {
      const height = c.height - 0.32
      for (const x of [-1.63, 1.63])
        box(
          0.14,
          height + 0.32,
          0.18,
          M.dark,
          x,
          (height + 0.32) / 2,
          0,
          g,
          0.02,
        )
      box(3.4, 0.32, 0.27, mat('#d6c4a6'), 0, height + 0.16, 0, g, 0.035)
      for (let i = -5; i <= 5; i++) {
        const stripe = box(
          0.1,
          0.29,
          0.02,
          M.dark,
          i * 0.29,
          height + 0.16,
          0.15,
          g,
        )
        stripe.rotation.z = -0.45
      }
    } else {
      box(2.96, 6.2, 0.48, mat('#aebcae'), 0, 3.1, 0, g, 0.07)
      for (const x of [-1.42, 1.42])
        box(0.11, 6.3, 0.59, M.dark, x, 3.15, 0, g, 0.02)
      for (const y of [0.9, 2.9, 4.9])
        box(2.9, 0.065, 0.52, M.white, 0, y, 0.01, g)
      box(2.2, 0.85, 0.06, mat('#d6c4a6'), 0, 1.8, 0.29, g, 0.035)
      const direction = (c.safeLane ?? (c.lane === 2 ? 1 : 2)) > c.lane ? 1 : -1
      for (const y of [-1, 1]) {
        const arm = box(
          0.68,
          0.12,
          0.04,
          M.dark,
          direction * 0.2,
          1.8 + y * 0.18,
          0.34,
          g,
          0.025,
        )
        arm.rotation.z = -direction * y * 0.55
      }
    }
    g.traverse((o) => {
      if (o.isMesh) o.material = o.material.clone()
    })
    scene.add(g)
    roadObjects.set(c.id, g)
    return g
  }
  function removeRoadObject(id, g) {
    scene.remove(g)
    g.traverse((o) => {
      if (o.isMesh) o.material.dispose()
    })
    roadObjects.delete(id)
  }
  let disposed = false
  return {
    resize(width, height) {
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.fov = camera.aspect < 1 ? 61 : 53
      camera.updateProjectionMatrix()
    },
    draw(s, reduced = false, pressed = false) {
      const z = -36 - s.distance,
        x = s.x
      placeWorld(x, z)
      updateSignals(0)
      clouds.position.set(x, 0, z)
      sun.position.set(x - 24, 34, z - 25)
      sun.target.position.set(x, 0, z - 12)
      const effect = motion(s, reduced, pressed)
      player.g.position.set(x, s.height, z)
      player.body.position.y = -effect.dip
      player.g.rotation.set(effect.pitch, effect.yaw, effect.roll)
      player.stunt.rotation.z = effect.stuntRoll
      player.g.scale.setScalar(1)
      jets.visible = effect.boost
      jets.scale.y = reduced ? 1 : 0.93 + Math.sin(s.time * 27) * 0.07
      player.wheels.forEach((w) => (w.rotation.x = -s.distance / 0.32))
      contact.position.set(x, 0.028, z)
      contact.scale.setScalar(1 + s.height * 0.045)
      contact.material.opacity = 0.7 - s.height * 0.065
      // Follow only a fraction of the lift so both the car and its shadow stay visible.
      const narrow = camera.aspect < 1
      camera.position.set(
        x * 0.2,
        (narrow ? 9 : 7.2) + s.height * 0.24,
        z + (narrow ? 18 : 14),
      )
      camera.lookAt(x * 0.18, 0.75 + s.height * 0.15, z - (narrow ? 10 : 9))
      const course = courseBetween(s.distance - 15, s.distance + 130, s.seed)
      for (const b of carBatches.values()) b.mesh.count = 0
      const visibleGhosts = new Set(),
        visibleRoad = new Set()
      for (const row of course.rows)
        for (const c of row.cars) {
          const protectedGroup = s.protectedGroups.has(row.groupId)
          if (c.type === 'wall' || c.type === 'gate') {
            const object = roadObject(c)
            object.position.set(c.x, 0, -36 - c.distance)
            object.traverse((o) => {
              if (o.isMesh) {
                o.material.transparent = protectedGroup
                o.material.opacity = protectedGroup ? 0.18 : 1
                o.material.depthWrite = !protectedGroup
                o.castShadow = !protectedGroup
              }
            })
            visibleRoad.add(c.id)
            continue
          }
          if (protectedGroup) {
            const ghost = ghostCar(c)
            ghost.position.set(c.x, 0, -36 - c.distance)
            visibleGhosts.add(c.id)
            continue
          }
          const parts = templates.get(
            `${c.type === 'truck' ? 1 : 0}:${c.color}`,
          )
          origin.makeTranslation(c.x, 0, -36 - c.distance)
          for (const part of parts) {
            const b = carBatches.get(part.key),
              i = b.mesh.count++
            if (i >= 256) throw Error('Traffic instance capacity exceeded')
            dummy.multiplyMatrices(origin, part.matrix)
            b.mesh.setMatrixAt(i, dummy)
          }
        }
      for (const [id, ghost] of ghostCars)
        if (!visibleGhosts.has(id)) removeGhost(id, ghost)
      for (const [id, object] of roadObjects)
        if (!visibleRoad.has(id)) removeRoadObject(id, object)
      for (const b of carBatches.values())
        b.mesh.instanceMatrix.needsUpdate = true
      let coinIndex = 0
      for (const p of [
        ...course.pickups.filter((p) => !s.collected.has(p.id)),
        ...s.coinFlights,
      ]) {
        const catching = p.at !== undefined,
          t = catching ? Math.min(1, (s.time - p.at) / 0.22) : 0
        if (t >= 1) continue
        const ease = 1 - (1 - t) ** 3,
          blend = reduced && catching ? 1 : ease,
          worldZ = -36 - p.distance
        coinPose.position.set(
          p.x + (x - p.x) * blend,
          p.height +
            1 +
            (s.height + 0.95 - p.height) * blend +
            (reduced
              ? 0
              : catching
                ? Math.sin(t * Math.PI) * 0.25
                : Math.sin(s.time * 2.5 + p.distance) * 0.045),
          worldZ + (z + 0.5 - worldZ) * blend,
        )
        coinPose.rotation.set(
          0,
          reduced ? 0.2 : s.time * 2.2 + p.distance * 0.08,
          0,
        )
        coinPose.scale.setScalar(1 - t * 0.85)
        coinPose.updateMatrix()
        if (coinIndex >= 32) throw Error('Coin instance capacity exceeded')
        for (const mesh of coinBatches)
          mesh.setMatrixAt(coinIndex, coinPose.matrix)
        coinIndex++
      }
      for (const mesh of coinBatches) {
        mesh.count = coinIndex
        mesh.instanceMatrix.needsUpdate = true
      }
      const coinAge = s.time - s.coinAt,
        glint = Math.max(0, 1 - coinAge / 0.28)
      glints.visible = !reduced && glint > 0
      glints.material.opacity = glint * 0.7
      for (let i = 0; i < 5; i++) {
        const a = (i * Math.PI * 2) / 5,
          r = 0.35 + coinAge * 2
        coinPose.position.set(
          x + Math.cos(a) * r,
          s.height + 1.95 + Math.sin(a) * 0.25 + coinAge * 0.3,
          z + 0.5 + Math.sin(a) * r * 0.5,
        )
        coinPose.rotation.set(0, a, coinAge * 2)
        coinPose.scale.setScalar(0.7 + glint * 0.3)
        coinPose.updateMatrix()
        glints.setMatrixAt(i, coinPose.matrix)
      }
      glints.instanceMatrix.needsUpdate = true
      const grant = Math.max(0, 1 - (s.time - s.shieldAt) / 0.6),
        hit = Math.max(0, 1 - (s.time - s.shieldHitAt) / 0.5),
        pulse = reduced ? 0 : hit * 0.28 + grant * 0.08
      shield.visible = s.shields > 0 || hit > 0
      shield.position.set(x, s.height + 0.95, z)
      shield.scale.set(1.35 + pulse, 1.12 + pulse, 2.6 + pulse)
      shield.material.opacity = 0.075 + grant * 0.09 + hit * 0.22
      renderer.render(scene, camera)
    },
    dispose() {
      if (disposed) return
      disposed = true
      for (const [id, ghost] of ghostCars) removeGhost(id, ghost)
      for (const [id, object] of roadObjects) removeRoadObject(id, object)
      const geometries = new Set(geos.values()),
        materials = new Set(mats.values()),
        textures = new Set()
      for (const root of ownedRoots)
        root.traverse((o) => {
          if (o.geometry) geometries.add(o.geometry)
          if (o.material) materials.add(o.material)
          if (o.isInstancedMesh) o.dispose()
          if (o.isLight && o.shadow) o.shadow.dispose()
        })
      for (const m of materials) {
        for (const v of Object.values(m)) if (v?.isTexture) textures.add(v)
        m.dispose()
      }
      textures.forEach((t) => t.dispose())
      geometries.forEach((g) => g.dispose())
      scene.clear()
      renderer.dispose()
    },
  }
}
