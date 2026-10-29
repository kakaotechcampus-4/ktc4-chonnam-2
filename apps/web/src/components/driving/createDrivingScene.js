import * as THREE from 'three';
import { GRID, signalAspect, signalPhase, pedestrianAspect, crossingPose, crossingOccupied } from './rules';
// Scene state is local to this instance. No analysis commands, timers or progress live here.
export function createDrivingScene(root, onUnavailable) {
    const canvas = root.querySelector('canvas'), events = new AbortController(), ownedRoots = [], cleanups = [];
    let renderer, scene, frame = 0, disposed = false;
    const listen = (target, type, handler) => target.addEventListener(type, handler, { signal: events.signal });
    function dispose() {
        if (disposed)
            return;
        disposed = true;
        cancelAnimationFrame(frame);
        events.abort();
        cleanups.forEach(fn => fn());
        const geometries = new Set(), materials = new Set(), textures = new Set();
        for (const parent of ownedRoots)
            parent.traverse(o => { if (o.geometry)
                geometries.add(o.geometry); if (o.material)
                for (const m of Array.isArray(o.material) ? o.material : [o.material])
                    materials.add(m); if (o.isInstancedMesh)
                o.dispose(); if (o.isLight && o.shadow)
                o.shadow.dispose(); });
        for (const m of materials) {
            for (const value of Object.values(m))
                if (value?.isTexture)
                    textures.add(value);
            m.dispose();
        }
        textures.forEach(t => t.dispose());
        geometries.forEach(g => g.dispose());
        scene?.clear();
        renderer?.dispose();
        renderer?.forceContextLoss();
        if (document.fullscreenElement && root.contains(document.fullscreenElement))
            document.exitFullscreen().catch(() => { });
    }
    try {
        scene = new THREE.Scene();
        ownedRoots.push(scene);
        scene.background = new THREE.Color('#c0e1f0');
        scene.fog = new THREE.Fog('#c0e1f0', 45, 112);
        renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
        renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.18;
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        const camera = new THREE.PerspectiveCamera(53, 1.6, .05, 220);
        scene.add(camera);
        scene.add(new THREE.HemisphereLight('#e2f0ff', '#c1bda1', 2.8));
        const sun = new THREE.DirectionalLight('#fff0d3', 2.1);
        sun.castShadow = true;
        sun.shadow.mapSize.set(1024, 1024);
        Object.assign(sun.shadow.camera, { left: -38, right: 38, top: 38, bottom: -38, near: 1, far: 120 });
        sun.shadow.normalBias = .05;
        sun.shadow.bias = -.00015;
        scene.add(sun, sun.target);
        const fill = new THREE.DirectionalLight('#d4e8ff', .6);
        fill.position.set(25, 8, 1);
        scene.add(fill);
        const mats = new Map(), geos = new Map();
        function mat(color, roughness = .78, metalness = 0) { const k = [color, roughness, metalness].join(':'); if (!mats.has(k))
            mats.set(k, new THREE.MeshStandardMaterial({ color, roughness, metalness })); return mats.get(k); }
        function rounded(w, h, d, r) { const k = [w, h, d, r].join(':'); if (geos.has(k))
            return geos.get(k); const g = new THREE.BoxGeometry(w, h, d, r ? 4 : 1, r ? 4 : 1, r ? 4 : 1); if (r) {
            const p = g.attributes.position, v = new THREE.Vector3(), q = new THREE.Vector3(), a = new THREE.Vector3(w / 2 - r, h / 2 - r, d / 2 - r);
            for (let i = 0; i < p.count; i++) {
                v.fromBufferAttribute(p, i);
                q.set(Math.max(-a.x, Math.min(a.x, v.x)), Math.max(-a.y, Math.min(a.y, v.y)), Math.max(-a.z, Math.min(a.z, v.z)));
                v.sub(q).normalize().multiplyScalar(r).add(q);
                p.setXYZ(i, v.x, v.y, v.z);
            }
            g.computeVertexNormals();
        } geos.set(k, g); return g; }
        const M = { road: mat('#78838a'), grass: mat('#93b57e'), sidewalk: mat('#e2dbca'), curb: mat('#eeece2'), line: mat('#f3efdf'), center: mat('#e2cf8d'), trunk: mat('#8b7961'), leaf: [mat('#65a282'), mat('#7db58b'), mat('#a0bc7b')], ivory: mat('#eee2cb'), peach: mat('#e0b9a4'), blue: mat('#a9ced6'), glass: mat('#809fab', .24, .2), silver: mat('#b9c7cd', .3, .65), dark: mat('#3b4852', .55), white: mat('#f0eee5') };
        const textureCanvas = document.createElement('canvas');
        textureCanvas.width = textureCanvas.height = 128;
        const textureCtx = textureCanvas.getContext('2d'), pixels = textureCtx.createImageData(128, 128);
        let seed = 17;
        for (let i = 0; i < pixels.data.length; i += 4) {
            seed = seed * 16807 % 2147483647;
            const n = 128 + seed % 21 - 10;
            pixels.data[i] = pixels.data[i + 1] = pixels.data[i + 2] = n;
            pixels.data[i + 3] = 255;
        }
        textureCtx.putImageData(pixels, 0, 0);
        const grain = new THREE.CanvasTexture(textureCanvas);
        grain.wrapS = grain.wrapT = THREE.RepeatWrapping;
        grain.colorSpace = THREE.SRGBColorSpace;
        M.road.map = grain;
        M.road.color.set('#adb8c0');
        const sphere = new THREE.SphereGeometry(1, 18, 12), trunkGeo = new THREE.CylinderGeometry(.12, .14, 2.7, 10);
        function mesh(geo, m, x, y, z, p) { const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); o.castShadow = true; o.receiveShadow = true; p.add(o); return o; }
        function box(w, h, d, m, x, y, z, p, r = 0) { return mesh(rounded(w, h, d, r), m, x, y, z, p); }
        function oval(xr, yr, zr, m, x, y, z, p) { const o = mesh(sphere, m, x, y, z, p); o.scale.set(xr, yr, zr); return o; }
        function tree(x, z, v, p) { const g = new THREE.Group(); g.position.set(x, 0, z); p.add(g); mesh(trunkGeo, M.trunk, 0, 1.35, 0, g); const h = 3.8 + v * .26; oval(.93, 1.03, .98, M.leaf[v % 3], .05, h - .15, 0, g); oval(.83, .9, .84, M.leaf[(v + 1) % 3], -.63, h - .52, .12, g); oval(.81, .84, .81, M.leaf[v % 3], .64, h - .43, -.09, g); oval(.85, .7, .82, M.leaf[v % 3], -.13, h - .87, .2, g); }
        function building(x, z, v, rot, p) { const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = rot; p.add(g); const ht = [5, 7, 5.8][v % 3], w = 6.7, d = 7; box(w, ht, d, [M.ivory, M.peach, M.blue][v % 3], 0, ht / 2, 0, g, .18); box(w + .25, .22, d + .23, M.white, 0, ht + .02, 0, g, .06); for (let y = 1.6; y < ht - 1; y += 1.6) {
            for (let a = -2; a <= 2; a += 2) {
                box(.95, 1, .025, M.glass, a, y, 3.52, g);
                box(.025, 1, 1.05, M.glass, 3.36, y, a, g);
                box(1.1, .09, .14, M.white, a, y - .55, 3.56, g);
            }
        } box(3.8, .14, .8, mat('#839f9c'), 0, 2.3, 3.7, g, .045); }
        const tile = new THREE.Group();
        ownedRoots.push(tile);
        const signalMaterial = new THREE.MeshBasicMaterial({ color: '#ffffff', toneMapped: false });
        const signalColor = new THREE.Color(), signalColors = ['#fb715f', '#ffcc52', '#7ae4a1', '#7ae4a1'];
        function updateSignals(time) {
            for (const b of signalBatches) {
                let n = 0;
                for (let ix = -1; ix <= 1; ix++)
                    for (let iz = -1; iz <= 1; iz++) {
                        const x = (gridX + ix) * GRID, z = (gridZ + iz) * GRID;
                        for (const s of b.signals) {
                            const a = signalAspect(s.axis, time, x, z);
                            let on, color;
                            if (s.kind === 'ped') {
                                const p = pedestrianAspect(s.axis, time, x, z);
                                on = s.index === 0 ? p.phase === 'red' : p.phase === 'walk' || p.phase === 'flash' && Math.floor(p.elapsed * 2) % 2 === 0;
                                color = s.index === 0 ? signalColors[0] : signalColors[3];
                            }
                            else {
                                on = [a.red, a.yellow, a.left, a.straight][s.index];
                                color = signalColors[s.index];
                            }
                            b.mesh.setColorAt(n++, signalColor.set(on ? color : '#263a3c'));
                        }
                    }
                b.mesh.instanceColor.needsUpdate = true;
            }
        }
        function litPart(o, axis, index, kind = 'vehicle') { o.userData.signal = { axis, index, kind }; o.castShadow = false; return o; }
        function pedestrianSignal(x, z, axis, p) {
            const g = new THREE.Group();
            g.position.set(x, 0, z);
            g.rotation.y = x > 0 ? -Math.PI / 2 : Math.PI / 2;
            p.add(g);
            mesh(new THREE.CylinderGeometry(.055, .075, 2.7, 8), M.dark, 0, 1.35, 0, g);
            box(.53, 1.12, .25, M.dark, 0, 2.65, 0, g, .07);
            for (const i of [0, 1]) {
                const y = 2.91 - i * .52;
                box(.40, .44, .018, mat('#233338'), 0, y, .135, g, .04);
                litPart(oval(.046, .046, .019, signalMaterial, 0, y + .13, .157, g), axis, i, 'ped');
                litPart(box(.065, .16, .018, signalMaterial, 0, y + .01, .158, g), axis, i, 'ped');
                for (const side of [-1, 1]) {
                    const arm = litPart(box(.035, .14, .018, signalMaterial, side * .07, y + .025, .158, g), axis, i, 'ped');
                    arm.rotation.z = i ? side * .7 : side * .12;
                    const leg = litPart(box(.04, .15, .018, signalMaterial, side * (i ? .059 : .029), y - .13, .158, g), axis, i, 'ped');
                    leg.rotation.z = i ? side * .5 : 0;
                }
            }
        }
        box(14, .1, 96, M.road, 0, -.04, 0, tile);
        box(96, .1, 14, M.road, 0, -.041, 0, tile);
        box(19, .09, 19, M.road, 0, -.02, 0, tile);
        for (const sx of [-1, 1])
            for (const sz of [-1, 1]) {
                box(38.8, .18, 38.8, M.sidewalk, sx * 28.6, .02, sz * 28.6, tile, .25);
                box(33, .07, 33, M.grass, sx * 31, .14, sz * 31, tile, .04);
            }
        for (let arm = 0; arm < 4; arm++) {
            const a = new THREE.Group();
            a.rotation.y = arm * Math.PI / 2;
            tile.add(a);
            for (const x of [-8.05, 8.05]) {
                box(2.1, .1, 38.8, M.road, x, -.04, -28.6, a);
                box(.09, .015, 32, M.line, x + Math.sign(x) * .87, .024, -31, a);
                for (const z of [-16, -28, -40, -47])
                    box(1.9, .018, .09, M.line, x, .024, z, a);
            }
            for (const x of [-7.0, 7.0])
                box(.11, .018, 37, M.line, x, .023, -29.5, a);
            for (const x of [-.12, .12])
                box(.08, .018, 36, M.center, x, .025, -30, a);
            for (const x of [-3.5, 3.5]) {
                box(.11, .02, 10, M.line, x, .025, -19, a);
                for (let z = -27; z >= -47; z -= 6)
                    box(.11, .02, 2.7, M.line, x, .025, z, a);
            }
            for (const x of [-9.2, 9.2])
                box(.22, .18, 35, M.curb, x, .13, -30.5, a, .07);
            for (let j = 0; j < 3; j++) {
                for (const sx of [-1, 1]) {
                    tree(sx * 10.3, -19 - j * 12, (j + arm) % 3, a);
                    box(1.5, .05, 1.5, mat('#a5b390'), sx * 10.3, .14, -19 - j * 12, a, .02);
                }
            }
            for (let j = 0; j < 3; j++)
                building(-17, -23 - j * 10.5, (arm + j) % 3, Math.PI / 2, a);
            building(17, -31, (arm + 1) % 3, -Math.PI / 2, a);
            oval(.8, .7, 2.1, mat('#83a27a'), 17, .8, -42, a);
            // Shoulder, stop line and raised pavement stay outside the vehicle's turning arc.
            for (let x = -6; x <= 6; x += 1.2)
                box(.63, .015, 2, M.line, x, .027, -10.5, a);
            box(6.6, .018, .28, M.line, -3.5, .03, -14, a);
            // Far-side signals remain visible from the driver's eye at the stop line.
            mesh(new THREE.CylinderGeometry(.085, .12, 5.5, 10), M.dark, -10.2, 2.9, 12, a);
            box(7, .14, .14, M.dark, -6.85, 5.6, 12, a, .04);
            box(3.08, .78, .34, M.dark, -3.5, 5.35, 12, a, .1);
            for (let i = 0; i < 4; i++) {
                const x = -2.39 - i * .74;
                if (i === 2) {
                    oval(.24, .24, .06, mat('#263a3c'), x, 5.35, 11.79, a);
                    litPart(box(.30, .065, .018, signalMaterial, x, 5.35, 11.72, a), arm % 2, i);
                    for (const s of [-1, 1]) {
                        const part = litPart(box(.17, .065, .018, signalMaterial, x + .10, 5.35 + s * .057, 11.72, a), arm % 2, i);
                        part.rotation.z = -s * Math.PI / 4;
                    }
                }
                else
                    litPart(oval(.24, .24, .06, signalMaterial, x, 5.35, 11.79, a), arm % 2, i);
            }
            for (const side of [-1, 1])
                pedestrianSignal(side * 9.85, -10.5, arm % 2, a);
            // A bench and small flowers make the pavement feel inhabited.
            box(.65, .14, 2, mat('#b28c6b'), 12.9, .64, -35, a, .05);
            box(.12, .55, 2, mat('#b28c6b'), 13.17, .99, -35, a, .035);
            for (const z of [-35.7, -34.3])
                box(.45, .49, .1, M.dark, 12.9, .37, z, a, .02);
            for (let j = 0; j < 4; j++) {
                mesh(new THREE.CylinderGeometry(.16, .13, .28, 8), mat('#cfaa8a'), 13, .3, -22 - j * .45, a);
                oval(.21, .15, .2, mat(j % 2 ? '#edcd83' : '#d5a29e'), 13, .57, -22 - j * .45, a);
            }
        }
        // Batch repeated scenery by geometry/material; camera movement does not rebuild the scene.
        tile.updateMatrixWorld(true);
        const batches = new Map();
        tile.traverse(o => { if (!o.isMesh)
            return; const key = o.geometry.uuid + o.material.uuid; if (!batches.has(key))
            batches.set(key, { geo: o.geometry, mat: o.material, transforms: [], signals: [] }); const b = batches.get(key); b.transforms.push(o.matrixWorld.clone()); if (o.userData.signal)
            b.signals.push(o.userData.signal); });
        const signalBatches = [...batches.values()].filter(b => b.mat === signalMaterial);
        for (const b of batches.values())
            if (b.mat === M.road) {
                const pos = b.geo.attributes.position, uv = b.geo.attributes.uv;
                for (let i = 0; i < pos.count; i++)
                    uv.setXY(i, pos.getX(i) / 4, pos.getZ(i) / 4);
                uv.needsUpdate = true;
            }
        for (const b of batches.values()) {
            b.mesh = new THREE.InstancedMesh(b.geo, b.mat, b.transforms.length * 9);
            b.mesh.castShadow = true;
            b.mesh.receiveShadow = true;
            b.mesh.frustumCulled = false;
            scene.add(b.mesh);
        }
        const ground = box(800, .1, 800, M.grass, 0, -.17, 0, scene);
        ground.castShadow = false;
        let gridX = 9999, gridZ = 9999;
        const trans = new THREE.Matrix4(), out = new THREE.Matrix4();
        function placeWorld(x, z) { const gx = Math.round(x / GRID), gz = Math.round(z / GRID); if (gx === gridX && gz === gridZ)
            return; gridX = gx; gridZ = gz; for (const b of batches.values()) {
            let n = 0;
            for (let ix = -1; ix <= 1; ix++)
                for (let iz = -1; iz <= 1; iz++) {
                    trans.makeTranslation((gx + ix) * GRID, 0, (gz + iz) * GRID);
                    for (const original of b.transforms) {
                        out.multiplyMatrices(trans, original);
                        b.mesh.setMatrixAt(n++, out);
                    }
                }
            b.mesh.instanceMatrix.needsUpdate = true;
        } ground.position.set(gx * GRID, -.17, gz * GRID); }
        const clouds = new THREE.Group();
        scene.add(clouds);
        for (let k = 0; k < 5; k++) {
            const angle = k * Math.PI * 2 / 5;
            for (let j = 0; j < 3; j++) {
                const c = oval(5, 1.6 + j % 2 * .7, 2.8, mat('#f9f8ee'), Math.cos(angle) * 100 + j * 4, 24 + k % 2 * 5, Math.sin(angle) * 100, clouds);
                c.castShadow = false;
                c.receiveShadow = false;
            }
        }
        const cockpit = new THREE.Group();
        camera.add(cockpit);
        const dash = mat('#48545e', .8), trim = mat('#8c9ca6', .35, .45), rubber = mat('#2c3740', .7);
        oval(2.9, .27, .62, dash, 0, -.91, -1.34, cockpit);
        oval(.53, .14, .24, rubber, -.30, -.70, -1.22, cockpit);
        box(3.8, .028, .08, trim, 0, -.755, -1.48, cockpit, .012);
        const steering = new THREE.Group();
        steering.position.set(-.31, -.49, -1.12);
        steering.rotation.x = -.10;
        cockpit.add(steering);
        mesh(new THREE.TorusGeometry(.30, .032, 16, 64), rubber, 0, 0, 0, steering);
        mesh(new THREE.TorusGeometry(.266, .005, 8, 64), trim, 0, 0, -.008, steering);
        box(.21, .17, .075, dash, 0, -.015, 0, steering, .045);
        for (const s of [-1, 1]) {
            const o = box(.20, .105, .045, dash, s * .18, .055, -.005, steering, .028);
            o.rotation.z = s * .22;
        }
        box(.053, .20, .045, dash, 0, -.17, -.004, steering, .02);
        box(.35, .19, .03, rubber, .45, -.69, -1.18, cockpit, .018);
        box(.25, .007, .005, mat('#8babb0'), .45, -.655, -1.161, cockpit, .002);
        cockpit.traverse(o => { if (o.isMesh) {
            o.castShadow = false;
            o.receiveShadow = false;
        } });
        // Rounded figures share geometry and are instanced, including animated limbs.
        function person(style) {
            const g = new THREE.Group(), skin = mat('#dab79a'), hair = mat(style ? '#655244' : '#4c4845'), shirt = mat(style ? '#cb8d78' : '#7eaab6'), pants = mat(style ? '#687d76' : '#637888');
            box(.43, .54, .28, shirt, 0, 1.08, 0, g, .09);
            box(.36, .14, .26, pants, 0, .77, 0, g, .05);
            oval(.185, .215, .17, skin, 0, 1.52, 0, g);
            oval(.194, .105, .181, hair, 0, 1.67, .018, g);
            oval(.045, .065, .043, skin, 0, 1.51, -.168, g);
            const limbs = [];
            for (const s of [-1, 1]) {
                const leg = new THREE.Group();
                leg.position.set(s * .105, .79, 0);
                g.add(leg);
                box(.145, .60, .17, pants, 0, -.30, 0, leg, .055);
                box(.18, .11, .30, M.white, 0, -.61, -.05, leg, .045);
                limbs.push(leg);
                const arm = new THREE.Group();
                arm.position.set(s * .27, 1.27, 0);
                g.add(arm);
                box(.14, .40, .16, shirt, 0, -.16, 0, arm, .05);
                oval(.068, .09, .07, skin, 0, -.40, 0, arm);
                limbs.push(arm);
            }
            if (style)
                box(.13, .25, .28, mat('#d8c797'), .31, .94, .05, g, .04);
            g.scale.setScalar(1.08);
            return { g, limbs };
        }
        const dogEarGeo = new THREE.ConeGeometry(.085, .19, 4), collarGeo = new THREE.TorusGeometry(.17, .027, 6, 16), tailGeo = new THREE.TorusGeometry(.15, .065, 8, 16, Math.PI * 1.7), leashGeo = new THREE.CylinderGeometry(.009, .009, 1, 5);
        function dog() {
            const g = new THREE.Group(), tan = mat('#c99e6e'), cream = mat('#efe3cb'), nose = mat('#484b49');
            oval(.20, .23, .40, tan, 0, .44, 0, g);
            oval(.18, .22, .16, cream, 0, .44, -.30, g);
            oval(.21, .22, .20, tan, 0, .69, -.40, g);
            oval(.16, .10, .12, cream, 0, .62, -.57, g);
            oval(.055, .04, .04, nose, 0, .67, -.67, g);
            for (const s of [-1, 1]) {
                const ear = mesh(dogEarGeo, tan, s * .13, .92, -.39, g);
                ear.rotation.z = s * -.15;
                oval(.023, .025, .015, nose, s * .11, .74, -.58, g);
            }
            const collar = mesh(collarGeo, mat('#6b9990'), 0, .58, -.34, g);
            collar.rotation.x = .6;
            const limbs = [];
            for (const x of [-.14, .14])
                for (const z of [-.23, .24]) {
                    const leg = new THREE.Group();
                    leg.position.set(x, .38, z);
                    g.add(leg);
                    box(.085, .28, .09, tan, 0, -.14, 0, leg, .025);
                    box(.10, .07, .15, cream, 0, -.29, -.025, leg, .025);
                    limbs.push(leg);
                }
            const tail = mesh(tailGeo, tan, 0, .70, .36, g);
            tail.rotation.y = Math.PI / 2;
            g.scale.setScalar(1.15);
            return { g, limbs, tail };
        }
        const streetActors = [], actorBatches = new Map();
        for (let cell = 0; cell < 9; cell++)
            for (let axis = 0; axis < 2; axis++) {
                const group = new THREE.Group(), owner = person(0), walker = person(1), oppositeWalker = person(0), pet = dog();
                group.add(owner.g, walker.g, oppositeWalker.g, pet.g);
                const leash = mesh(leashGeo, mat('#627974'), 0, 0, 0, group);
                leash.castShadow = false;
                ownedRoots.push(group);
                streetActors.push({ cell, axis, group, owner, walker, oppositeWalker, pet, leash });
                group.traverse(o => { if (!o.isMesh)
                    return; const key = o.geometry.uuid + o.material.uuid; if (!actorBatches.has(key))
                    actorBatches.set(key, { geo: o.geometry, mat: o.material, parts: [] }); actorBatches.get(key).parts.push(o); });
            }
        for (const b of actorBatches.values()) {
            b.mesh = new THREE.InstancedMesh(b.geo, b.mat, b.parts.length);
            b.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            b.mesh.castShadow = true;
            b.mesh.receiveShadow = true;
            b.mesh.frustumCulled = false;
            scene.add(b.mesh);
        }
        const leashA = new THREE.Vector3(), leashB = new THREE.Vector3(), leashDelta = new THREE.Vector3(), upAxis = new THREE.Vector3(0, 1, 0);
        function stroll(time, phase) { const t = (time * .82 + phase) % 44; return { z: 19 + (t < 22 ? t : 44 - t), forward: t < 22 }; }
        function walkPerson(p, time, phase) { const s = Math.sin(time * 4.7 + phase) * .32; p.limbs[0].rotation.x = s; p.limbs[2].rotation.x = -s; p.limbs[1].rotation.x = -s * .8; p.limbs[3].rotation.x = s * .8; }
        function updateStreetLife(time) {
            updateSignals(time);
            for (const a of streetActors) {
                const gx = gridX + Math.floor(a.cell / 3) - 1, gz = gridZ + a.cell % 3 - 1, phase = ((gx * 17 + gz * 11 + a.axis * 9) % 22 + 22) % 22, p = stroll(time, phase);
                a.group.position.set(gx * GRID, .12, gz * GRID);
                a.group.rotation.y = a.axis * Math.PI / 2;
                a.owner.g.position.set(11.65, 0, p.z);
                a.owner.g.rotation.y = p.forward ? Math.PI : 0;
                walkPerson(a.owner, time, phase);
                // Walkers start only during steady green; flashing green clears existing crossings.
                for (const [walker, armSide] of [[a.walker, 1], [a.oppositeWalker, -1]]) {
                    const crossing = crossingPose(time, gx * GRID, gz * GRID, a.axis, armSide);
                    walker.g.position.set(crossing.x, 0, crossing.z);
                    walker.g.rotation.y = crossing.side * Math.PI / 2;
                    if (crossing.moving)
                        walkPerson(walker, time, phase + 1.3 + armSide);
                    else
                        walker.limbs.forEach(l => l.rotation.x = 0);
                }
                a.pet.g.position.set(12.35, 0, p.z + (p.forward ? .9 : -.9));
                a.pet.g.rotation.y = p.forward ? Math.PI : 0;
                a.pet.limbs.forEach((leg, i) => leg.rotation.x = Math.sin(time * 6 + phase + (i === 0 || i === 3 ? 0 : Math.PI)) * .34);
                a.pet.tail.rotation.z = Math.sin(time * 2.5) * .12;
                leashA.set(11.65 + (p.forward ? .29 : -.29), .94, p.z);
                leashB.set(12.35, .71, p.z + (p.forward ? .9 : -.9) + (p.forward ? .38 : -.38));
                leashDelta.subVectors(leashB, leashA);
                a.leash.position.copy(leashA).add(leashB).multiplyScalar(.5);
                a.leash.scale.y = leashDelta.length();
                a.leash.quaternion.setFromUnitVectors(upAxis, leashDelta.normalize());
                a.group.updateMatrixWorld(true);
            }
            for (const b of actorBatches.values()) {
                b.parts.forEach((part, i) => b.mesh.setMatrixAt(i, part.matrixWorld));
                b.mesh.instanceMatrix.needsUpdate = true;
            }
        }
        // Small, independent cars keep their world positions as the surrounding scenery is recycled.
        const trafficCars = [], trafficBatches = new Map(), carPaints = ['#93b7a7', '#d6c4a6', '#8ba8bd', '#c69e8c'], tireGeo = new THREE.CylinderGeometry(.32, .32, .19, 16), hubGeo = new THREE.CylinderGeometry(.16, .16, .205, 12), tailMaterial = new THREE.MeshBasicMaterial({ color: '#ffffff', toneMapped: false });
        function makeTrafficCar(index) {
            const g = new THREE.Group(), paint = mat(carPaints[index % 4], .4, .08), glass = mat('#617c88', .3, .15), tires = mat('#354049'), rims = mat('#b1c0c3', .4, .35), wheels = [];
            box(1.82, .51, 4.05, paint, 0, .66, 0, g, .2);
            box(1.69, .16, 3.80, paint, 0, .94, -.05, g, .07);
            box(1.48, .58, 2.13, glass, 0, 1.22, .17, g, .16);
            box(1.43, .12, 1.69, paint, 0, 1.51, .20, g, .05);
            for (const x of [-.73, .73]) {
                box(.065, .54, .12, paint, x, 1.23, .16, g, .02);
                box(.065, .46, .12, paint, x, 1.22, .91, g, .02);
                box(.23, .10, .25, paint, x * 1.22, 1.10, -.71, g, .045);
            }
            box(.88, .14, .035, M.dark, 0, .57, -2.025, g, .025);
            box(.34, .12, .04, M.white, 0, .58, 2.03, g, .015);
            for (const s of [-1, 1]) {
                box(.39, .14, .05, mat('#f0e6bc'), s * .59, .78, -2.025, g, .045);
                const tail = box(.39, .13, .05, tailMaterial, s * .59, .80, 2.03, g, .035);
                tail.userData.brake = true;
            }
            for (const x of [-.84, .84])
                for (const z of [-1.24, 1.26]) {
                    const wheel = new THREE.Group();
                    wheel.position.set(x, .36, z);
                    g.add(wheel);
                    mesh(tireGeo, tires, 0, 0, 0, wheel).rotation.z = Math.PI / 2;
                    mesh(hubGeo, rims, 0, 0, 0, wheel).rotation.z = Math.PI / 2;
                    wheels.push(wheel);
                }
            ownedRoots.push(g);
            const car = { g, wheels, anchor: { x: 0, z: 0 }, dir: 0, progress: 0, lane: 5.25, speed: 7, cruise: 7.2 + index % 3 * .45, entered: false, braking: false, travel: 0, index };
            g.traverse(o => { if (!o.isMesh)
                return; const key = o.geometry.uuid + o.material.uuid; if (!trafficBatches.has(key))
                trafficBatches.set(key, { geo: o.geometry, mat: o.material, parts: [] }); trafficBatches.get(key).parts.push({ part: o, car }); });
            return car;
        }
        for (let i = 0; i < 16; i++)
            trafficCars.push(makeTrafficCar(i));
        for (const b of trafficBatches.values()) {
            b.mesh = new THREE.InstancedMesh(b.geo, b.mat, b.parts.length);
            b.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            b.mesh.castShadow = true;
            b.mesh.receiveShadow = true;
            b.mesh.frustumCulled = false;
            scene.add(b.mesh);
        }
        function carPose(c) { const h = vectors[c.dir], r = right(h); return point(c.anchor, h, c.progress, r, c.lane); }
        function carJunction(c) { const h = vectors[c.dir]; return point(c.anchor, h, GRID, right(h), 0); }
        function setTraffic(c, x, z, dir, progress, lane) { Object.assign(c, { anchor: { x, z }, dir, progress, lane, speed: c.cruise, entered: progress > 79.5, braking: false, travel: 0 }); }
        let trafficReady = false, trafficSeed = 31;
        function trafficRandom() { trafficSeed = trafficSeed * 16807 % 2147483647; return trafficSeed / 2147483647; }
        function initTraffic() {
            if (trafficReady)
                return;
            trafficReady = true;
            const specs = [[0, 0, 0, 64, 5.25], [0, 0, 0, 84, 1.75], [0, -96, 2, 28, 5.25], [0, -96, 2, 8, 1.75], [-96, -96, 1, 50, 5.25], [96, -96, 3, 60, 1.75], [0, -96, 0, 36, 5.25], [-96, 0, 1, 36, 1.75], [96, 0, 3, 30, 5.25], [-96, -96, 0, 24, 1.75], [96, -96, 2, 44, 5.25], [0, -192, 2, 28, 1.75], [0, -192, 2, 52, 5.25], [0, -192, 2, 8, 5.25], [-96, 96, 0, 32, 5.25], [96, -192, 2, 28, 1.75]];
            specs.forEach((s, i) => setTraffic(trafficCars[i], ...s));
        }
        function recycleTraffic(c, player) {
            const p = carPose(c), distance = Math.hypot(p.x - player.x, p.z - player.z), oncoming = [2, 3, 11, 12, 13].includes(c.index);
            if (oncoming) {
                const h = vectors[state.dir], r = right(h), along = (p.x - player.x) * h.x + (p.z - player.z) * h.z, side = (p.x - state.anchor.x) * r.x + (p.z - state.anchor.z) * r.z, dir = (state.dir + 2) % 4;
                if (distance < 113 && (state.turn || along > -8 || distance < 20) || c.dir === dir && Math.abs(side + c.lane) < .1 && along > 0 && along < 210)
                    return;
                // Reuse only cars behind the camera or beyond the fog, including after turns.
                for (let attempt = 0; attempt < 24; attempt++) {
                    const ahead = state.progress + 118 + trafficRandom() * 62, block = Math.ceil(ahead / GRID), progress = block * GRID - ahead, lane = attempt % 2 ? 1.75 : 5.25, anchor = point(state.anchor, h, block * GRID, r, 0), q = point(anchor, vectors[dir], progress, right(vectors[dir]), lane);
                    if (progress < 18 || progress > 73 || trafficCars.some(o => o !== c && Math.hypot(carPose(o).x - q.x, carPose(o).z - q.z) < 18))
                        continue;
                    setTraffic(c, anchor.x, anchor.z, dir, progress, lane);
                    return;
                }
                return;
            }
            if (distance < 170)
                return;
            for (let attempt = 0; attempt < 24; attempt++) {
                const gx = Math.round(player.x / GRID) + Math.floor(trafficRandom() * 3) - 1, gz = Math.round(player.z / GRID) + Math.floor(trafficRandom() * 3) - 1, dir = Math.floor(trafficRandom() * 4), progress = 18 + trafficRandom() * 55, lane = trafficRandom() < .5 ? 1.75 : 5.25, h = vectors[dir], p = point({ x: gx * GRID, z: gz * GRID }, h, progress, right(h), lane), distance = Math.hypot(p.x - player.x, p.z - player.z);
                if (distance < 113 || distance > 155 || trafficCars.some(o => o !== c && Math.hypot(carPose(o).x - p.x, carPose(o).z - p.z) < 13))
                    continue;
                setTraffic(c, gx * GRID, gz * GRID, dir, progress, lane);
                return;
            }
        }
        function junctionConflict(c, j) {
            for (const o of trafficCars) {
                if (o === c || !o.entered || o.dir % 2 === c.dir % 2)
                    continue;
                const q = carJunction(o);
                if (Math.hypot(q.x - j.x, q.z - j.z) < 2)
                    return true;
            }
            const q = state.turn ? state.turn.j : upcoming();
            return (state.entered || state.turn) && Math.hypot(q.x - j.x, q.z - j.z) < 2 && (!!state.turn || state.queued !== 0 || state.dir % 2 !== c.dir % 2);
        }
        function stepTraffic(dt) {
            initTraffic();
            const player = pose();
            for (const c of trafficCars) {
                recycleTraffic(c, player);
                const p = carPose(c), h = vectors[c.dir], r = right(h), j = carJunction(c), red = !c.entered && (signalPhase(c.dir, state.clock, j.x, j.z) !== 'green' || junctionConflict(c, j));
                let free = red ? Math.max(0, 79.5 - c.progress) : Infinity;
                for (const o of trafficCars) {
                    if (o === c)
                        continue;
                    const q = carPose(o), dx = q.x - p.x, dz = q.z - p.z, along = dx * h.x + dz * h.z, lateral = Math.abs(dx * r.x + dz * r.z);
                    if (along > 0 && lateral < 2.05)
                        free = Math.min(free, Math.max(0, along - 6.8));
                }
                const dx = player.x - p.x, dz = player.z - p.z, along = dx * h.x + dz * h.z, lateral = Math.abs(dx * r.x + dz * r.z);
                if (along > 0 && lateral < 2.1)
                    free = Math.min(free, Math.max(0, along - 7));
                const previousSpeed = c.speed, target = Math.min(c.cruise, Math.sqrt(5.6 * free));
                c.speed += (target - c.speed) * (1 - Math.exp(-dt * 2.6));
                const distance = Math.min(c.speed * dt, free);
                if (distance < .001 && target < .1)
                    c.speed = 0;
                c.progress += distance;
                c.travel += distance;
                c.braking = c.speed < previousSpeed - .015 || c.speed < .2;
                if (!red && c.progress > 79.5)
                    c.entered = true;
                if (c.progress >= 108) {
                    c.anchor.x += h.x * GRID;
                    c.anchor.z += h.z * GRID;
                    c.progress -= GRID;
                    c.entered = false;
                }
            }
        }
        function trafficLaneClear(goal, horizon = 0) { const p = pose(), h = vectors[state.dir], r = right(h); return !trafficCars.some(c => { const q = carPose(c), dx = q.x - p.x, dz = q.z - p.z, along = dx * h.x + dz * h.z, lateral = dx * r.x + dz * r.z, heading = vectors[c.dir], future = along + (c.speed * (heading.x * h.x + heading.z * h.z) - state.speed) * horizon; return Math.min(along, future) < 15 && Math.max(along, future) > -10 && Math.abs(lateral - (goal - state.lane)) < 2.1; }); }
        function trafficForwardGap() { const p = pose(), h = vectors[state.dir], r = right(h); let free = Infinity; for (const c of trafficCars) {
            const q = carPose(c), dx = q.x - p.x, dz = q.z - p.z, along = dx * h.x + dz * h.z, lateral = Math.abs(dx * r.x + dz * r.z);
            if (along > 0 && lateral < 2.1)
                free = Math.min(free, Math.max(0, along - 7));
        } return free; }
        function trafficIntersectionClear(j, choice = state.queued) {
            for (const c of trafficCars) {
                const q = carPose(c), cj = carJunction(c), sameJunction = Math.hypot(cj.x - j.x, cj.z - j.z) < 2;
                if (c.entered && sameJunction && (c.dir % 2 !== state.dir % 2 || choice < 0 && c.dir !== state.dir))
                    return false;
                if (choice > 0 && sameJunction && c.dir % 2 !== state.dir % 2 && c.progress > 65 && c.speed > .5 && signalPhase(c.dir, state.clock, j.x, j.z) === 'green')
                    return false;
                if (choice !== 0) {
                    const nh = vectors[(state.dir + choice + 4) % 4], nr = right(nh), dx = q.x - j.x, dz = q.z - j.z, ahead = dx * nh.x + dz * nh.z, side = dx * nr.x + dz * nr.z;
                    if (ahead > -2 && ahead < 22 && Math.abs(side - (choice > 0 ? 5.25 : 1.75)) < 2.1)
                        return false;
                }
            }
            return true;
        }
        const brakeColor = new THREE.Color();
        function drawTraffic() { initTraffic(); for (const c of trafficCars) {
            const p = carPose(c), h = vectors[c.dir];
            c.g.position.set(p.x, 0, p.z);
            c.g.rotation.y = -Math.atan2(h.x, -h.z);
            c.wheels.forEach(w => w.rotation.x = -c.travel / .32);
            c.g.updateMatrixWorld(true);
        } for (const b of trafficBatches.values()) {
            b.parts.forEach(({ part, car }, i) => { b.mesh.setMatrixAt(i, part.matrixWorld); if (b.mat === tailMaterial)
                b.mesh.setColorAt(i, brakeColor.set(car.braking ? '#f27b68' : '#ae625a')); });
            b.mesh.instanceMatrix.needsUpdate = true;
            if (b.mesh.instanceColor)
                b.mesh.instanceColor.needsUpdate = true;
        } }
        const steerButtons = [...root.querySelectorAll('[data-steer]')], gearButtons = [...root.querySelectorAll('[data-gear]')], motionButton = root.querySelector('.motion'), fullscreenButton = root.querySelector('.fullscreen'), message = root.querySelector('.drive-message'), media = root.querySelector('.media');
        const reduced = matchMedia('(prefers-reduced-motion: reduce)');
        const state = { anchor: { x: 0, z: 0 }, dir: 0, progress: 36, lane: 5.25, targetLane: 5.25, speed: 7, queued: 0, turn: null, gear: 'D', parking: 'none', parkGoal: 0, entered: false, waitingSignal: false, waitingTraffic: false, stopDwell: 0, rightReleased: false, clock: 0, paused: reduced.matches, completed: false, turns: 0 };
        let visible = true, last = 0, wheelAngle = 0;
        const vectors = [{ x: 0, z: -1 }, { x: 1, z: 0 }, { x: 0, z: 1 }, { x: -1, z: 0 }];
        const right = h => ({ x: -h.z, z: h.x });
        const point = (a, h, n, r, l) => ({ x: a.x + h.x * n + r.x * l, z: a.z + h.z * n + r.z * l });
        function upcoming() { const h = vectors[state.dir]; return point(state.anchor, h, GRID, right(h), 0); }
        function resetIntersection() { state.entered = false; state.stopDwell = 0; state.rightReleased = false; }
        function movementCrossings(dir, choice) { const h = vectors[dir], nh = vectors[(dir + choice + 4) % 4]; return [{ axis: dir % 2, side: dir % 2 ? -h.x : -h.z }, { axis: (dir + choice + 4) % 2, side: (dir + choice + 4) % 2 ? nh.x : nh.z }]; }
        function rightPathClear(j) {
            // Check the entry AND exit crossing. A parallel walk signal is not a blanket red for cars.
            // Wait for actual walkers / people starting, including the time needed to clear the turn.
            for (const c of movementCrossings(state.dir, 1))
                for (let after = 0; after <= 12; after += .25)
                    if (crossingOccupied(state.clock + after, j, c.axis, c.side))
                        return false;
            return trafficIntersectionClear(j, 1);
        }
        function say(text) { if (message.textContent !== text)
            message.textContent = text; }
        function steeringMode() { return GRID - state.progress <= 44 && state.progress >= 18 ? 'turn' : 'lane'; }
        function steeringDisabled(direction) {
            const remaining = GRID - state.progress, goal = direction < 0 ? 1.75 : 5.25;
            if (state.turn || state.entered || state.completed || state.parking !== 'none' || state.progress < 18)
                return true;
            if (steeringMode() === 'lane')
                return Math.abs(state.targetLane - goal) < .01;
            // A last-second input cannot cut across the solid lane separator at the stop line.
            return state.queued !== direction && remaining < 36 && Math.abs(state.lane - goal) > .15;
        }
        function sync() {
            const mode = steeringMode();
            steerButtons.forEach(b => {
                const direction = Number(b.dataset.steer), selected = mode === 'turn' && state.queued === direction;
                b.dataset.mode = mode;
                b.disabled = steeringDisabled(direction);
                b.setAttribute('aria-pressed', String(selected));
                b.setAttribute('aria-label', mode === 'lane' ? (direction < 0 ? '왼쪽 차선으로 이동' : '오른쪽 차선으로 이동') : selected ? '회전 선택 취소 · 직진' : direction < 0 ? '다음 교차로에서 좌회전' : '다음 교차로에서 우회전');
            });
            gearButtons.forEach(b => { b.disabled = state.completed; b.setAttribute('aria-pressed', String(b.dataset.gear === state.gear)); });
            motionButton.disabled = state.completed;
            motionButton.setAttribute('aria-label', state.paused ? '주행 화면 재생' : '주행 화면 일시정지');
            motionButton.setAttribute('aria-pressed', String(state.paused));
        }
        function steer(direction) {
            if (steeringDisabled(direction))
                return;
            if (steeringMode() === 'turn' && state.queued === direction) {
                state.queued = 0;
                state.rightReleased = false;
                say('회전 선택을 취소했어요. 직진합니다.');
            }
            else {
                const goal = direction < 0 ? 1.75 : 5.25;
                if (Math.abs(state.lane - goal) > .15 && !trafficLaneClear(goal)) {
                    say('옆 차가 지나간 뒤 이동할 수 있어요.');
                    return;
                }
                state.targetLane = goal;
                if (steeringMode() === 'turn') {
                    state.queued = direction;
                    state.rightReleased = false;
                    say(direction < 0 ? '좌회전을 선택했어요. 좌회전 신호에 출발합니다.' : '우회전을 선택했어요. 보행자와 다른 차에 양보합니다.');
                }
                else
                    say(direction < 0 ? '왼쪽 차선으로 이동합니다.' : '오른쪽 차선으로 이동합니다.');
            }
            sync();
        }
        function startPullOver() { state.parking = 'outer'; state.targetLane = 5.25; say('2차선을 거쳐 갓길에 천천히 정차해요.'); }
        function requestGear(gear) {
            state.gear = gear;
            if (gear === 'P') {
                if (!state.turn) {
                    state.queued = 0;
                    state.rightReleased = false;
                }
                if (state.lane > 5.35 && !state.turn) {
                    state.parking = 'shoulder';
                    state.targetLane = 8;
                }
                else {
                    state.parking = 'waiting';
                    say('계속 주행하며 안전하게 갓길로 이동할 공간을 찾습니다.');
                }
            }
            else {
                if (['parked', 'braking', 'outer', 'shoulder'].includes(state.parking)) {
                    state.parking = 'merging';
                    state.targetLane = 5.25;
                    say('D · 2차선으로 천천히 합류해요.');
                }
                else {
                    state.parking = 'none';
                    say('D · 다시 알아서 주행해요.');
                }
            }
        }
        function setGear(gear) { if (state.completed || state.gear === gear)
            return; requestGear(gear); sync(); schedule(); }
        function beginTurn() { const h = vectors[state.dir], r = right(h), j = point(state.anchor, h, GRID, r, 0), choice = state.queued, dir = (state.dir + choice + 4) % 4, nh = vectors[dir], nr = right(nh), lane = choice > 0 ? 5.25 : 1.75; const start = point(j, h, -12, r, state.lane), end = point(j, nh, 12, nr, lane), radius = choice > 0 ? 12 - state.lane : 12 + state.lane, k = radius * .55228475; state.turn = { choice, dir, j, lane, start, end, c1: point(start, h, k, r, 0), c2: point(end, nh, -k, nr, 0), t: 0, cruise: choice > 0 ? 3.3 : 6, duration: choice > 0 ? 3.2 : 4.0 }; say(choice > 0 ? '주변을 살피며 천천히 우회전해요.' : '교차로에서 천천히 좌회전해요.'); sync(); }
        function bezier(t) { const b = state.turn, u = 1 - t; const pos = { x: u * u * u * b.start.x + 3 * u * u * t * b.c1.x + 3 * u * t * t * b.c2.x + t * t * t * b.end.x, z: u * u * u * b.start.z + 3 * u * u * t * b.c1.z + 3 * u * t * t * b.c2.z + t * t * t * b.end.z }; const dx = 3 * u * u * (b.c1.x - b.start.x) + 6 * u * t * (b.c2.x - b.c1.x) + 3 * t * t * (b.end.x - b.c2.x), dz = 3 * u * u * (b.c1.z - b.start.z) + 6 * u * t * (b.c2.z - b.c1.z) + 3 * t * t * (b.end.z - b.c2.z); return { ...pos, heading: Math.atan2(dx, -dz) }; }
        function tick(dt) {
            if (state.paused || state.completed)
                return;
            const wasWaiting = state.waitingSignal;
            state.clock += dt;
            state.waitingSignal = false;
            state.waitingTraffic = false;
            if (state.turn) {
                stepTraffic(dt);
                state.speed += (state.turn.cruise - state.speed) * (1 - Math.exp(-dt * 2.6));
                state.turn.t = Math.min(1, state.turn.t + dt / state.turn.duration * (state.speed / state.turn.cruise));
                if (state.turn.t >= 1) {
                    const t = state.turn;
                    state.anchor = t.j;
                    state.dir = t.dir;
                    state.progress = 12;
                    state.lane = state.targetLane = t.lane;
                    state.queued = 0;
                    state.turn = null;
                    resetIntersection();
                    state.turns++;
                }
                sync();
                return;
            }
            const remaining = GRID - state.progress, j = upcoming();
            stepTraffic(dt);
            // Reserve enough clear road for both lane changes; otherwise keep driving to the next block.
            if (state.parking === 'waiting' && state.progress >= 18 && state.progress < 50 && trafficLaneClear(5.25, 2.5))
                startPullOver();
            if (state.parking === 'outer' && Math.abs(state.lane - 5.25) < .08) {
                state.lane = state.targetLane = 5.25;
                if (state.progress < 60 && trafficLaneClear(8, 2)) {
                    state.parking = 'shoulder';
                    state.targetLane = 8;
                }
                else
                    state.parking = 'waiting';
            }
            if (state.parking === 'shoulder' && Math.abs(state.lane - 8) < .04) {
                state.lane = state.targetLane = 8;
                state.parking = 'braking';
                state.parkGoal = state.progress + 5;
            }
            if (state.parking === 'merging' && Math.abs(state.lane - 5.25) < .04) {
                state.lane = state.targetLane = 5.25;
                state.parking = 'none';
                say('주행 차선에 합류했어요.');
            }
            const pulling = state.parking === 'outer' || state.parking === 'shoulder', braking = state.parking === 'braking', parked = state.parking === 'parked', aspect = signalAspect(state.dir, state.clock, j.x, j.z);
            if (!state.entered)
                state.rightReleased = state.queued === 1 && state.parking === 'none' && aspect.red && !aspect.yellow && state.stopDwell >= 1.1 && rightPathClear(j);
            let allowed = state.queued < 0 ? aspect.left && aspect.remaining > 1.5 : state.queued > 0 ? (aspect.straight || state.rightReleased) && rightPathClear(j) : aspect.straight;
            const red = !state.entered && !allowed;
            const junctionBlocked = !state.entered && !trafficIntersectionClear(j), laneBlocked = Math.abs(state.targetLane - state.lane) > .04 && !trafficLaneClear(state.targetLane), free = trafficForwardGap();
            let target = parked ? 0 : state.parking === 'outer' ? 5.5 : state.parking === 'shoulder' || braking ? 3.6 : state.parking === 'merging' ? 3 : 7;
            if (state.queued && Math.abs(state.targetLane - state.lane) > .08)
                target = Math.min(target, 3.2);
            if (state.queued === 1 && remaining < 29)
                target = Math.min(target, state.rightReleased ? 2.6 : 3.3);
            if (braking)
                target = Math.min(target, Math.sqrt(4 * Math.max(0, state.parkGoal - state.progress)));
            if (red || junctionBlocked)
                target = Math.min(target, Math.sqrt(6.4 * Math.max(0, remaining - 16.5)));
            target = Math.min(target, Math.sqrt(5.6 * free));
            // An occupied adjacent lane is not a reason to stop in a travel lane.
            if (laneBlocked && state.parking === 'merging' && state.lane >= 7.2)
                target = 0;
            if ((free < 2 || junctionBlocked && remaining < 17) && !parked)
                state.waitingTraffic = true;
            state.speed += (target - state.speed) * (1 - Math.exp(-dt * 3.1));
            if (target === 0 && state.speed < .08)
                state.speed = 0;
            const latRate = pulling || state.parking === 'merging' ? 2.2 * Math.min(1, state.speed / 3) : 2.4 * (state.speed / 7);
            if (!laneBlocked)
                state.lane += (state.targetLane - state.lane) * (1 - Math.exp(-dt * latRate));
            const before = state.progress;
            state.progress += Math.min(state.speed * dt, free);
            if (free < .01)
                state.speed = 0;
            if (braking && state.progress >= state.parkGoal) {
                state.progress = state.parkGoal;
                state.speed = 0;
                state.parking = 'parked';
                say('주차 공간에 정차했어요.');
            }
            if (red && state.progress >= GRID - 16.5) {
                state.progress = GRID - 16.5;
                state.speed = 0;
                state.waitingSignal = true;
                if (aspect.red && !aspect.yellow)
                    state.stopDwell += dt;
            }
            if (junctionBlocked && state.progress >= GRID - 16.5) {
                state.progress = GRID - 16.5;
                state.speed = 0;
                state.waitingTraffic = true;
            }
            if (state.waitingSignal && !wasWaiting)
                say(pedestrianAspect(state.dir % 2, state.clock, j.x, j.z).phase !== 'red' || state.queued === 1 && !rightPathClear(j) ? '보행자와 다른 차에 양보하며 기다립니다.' : state.queued < 0 ? '좌회전 신호를 기다립니다.' : '신호와 교차로 상황을 확인하며 정지합니다.');
            if (wasWaiting && !state.waitingSignal)
                say('통행 가능한 상태를 확인했어요. 출발합니다.');
            if (!red && !junctionBlocked && before <= GRID - 16.5 && state.progress > GRID - 16.5)
                state.entered = true;
            if (state.queued && state.progress >= GRID - 12 && state.parking === 'none') {
                state.progress = GRID - 12;
                if (trafficIntersectionClear(j))
                    beginTurn();
                else {
                    state.speed = 0;
                    state.waitingTraffic = true;
                }
            }
            else if (state.progress >= GRID + 12) {
                const h = vectors[state.dir];
                state.anchor.x += h.x * GRID;
                state.anchor.z += h.z * GRID;
                state.progress -= GRID;
                resetIntersection();
            }
            sync();
        }
        function pose() { if (state.turn)
            return bezier(state.turn.t); const h = vectors[state.dir], r = right(h); const p = point(state.anchor, h, state.progress, r, state.lane); return { ...p, heading: Math.atan2(h.x, -h.z) }; }
        const wheelAnchor = new THREE.Vector3();
        function placeWheelControls() {
            const w = media.clientWidth, h = media.clientHeight;
            camera.updateMatrixWorld(true);
            for (const b of steerButtons) {
                wheelAnchor.set(Number(b.dataset.steer) * .18, .055, .028);
                steering.localToWorld(wheelAnchor);
                wheelAnchor.project(camera);
                b.style.left = ((wheelAnchor.x + 1) * w / 2) + 'px';
                b.style.top = ((1 - wheelAnchor.y) * h / 2) + 'px';
            }
        }
        function draw() { if (disposed)
            return; const p = pose(); placeWorld(p.x, p.z); updateStreetLife(state.clock); drawTraffic(); camera.position.set(p.x, 1.50, p.z); camera.rotation.set(-.001, -p.heading, 0, 'YXZ'); clouds.position.set(p.x, 0, p.z); sun.position.set(p.x - 24, 34, p.z - 25); sun.target.position.set(p.x, 0, p.z - 12); const steer = state.turn ? -state.turn.choice * .5 * Math.sin(Math.PI * state.turn.t) : -(state.targetLane - state.lane) * .16; wheelAngle += (steer - wheelAngle) * .16; steering.rotation.z = wheelAngle; placeWheelControls(); renderer.render(scene, camera); }
        function resize() { if (disposed)
            return; const r = media.getBoundingClientRect(); if (!r.width || !r.height)
            return; renderer.setSize(r.width, r.height, false); camera.aspect = r.width / r.height; camera.updateProjectionMatrix(); const scale = Math.min(1, Math.max(r.width / 600, 160 / r.height)); steering.scale.setScalar(scale); steering.position.x = -.179 * camera.aspect; steering.position.y = r.height < 340 ? -.56 + 31.25 / r.height - .055 * scale : -.49; draw(); }
        const resizeObserver = new ResizeObserver(resize);
        resizeObserver.observe(media);
        cleanups.push(() => resizeObserver.disconnect());
        const observer = new IntersectionObserver(es => { visible = es[0].isIntersecting; if (visible)
            schedule();
        else if (frame) {
            cancelAnimationFrame(frame);
            frame = 0;
            last = 0;
        } }, { threshold: 0 });
        observer.observe(canvas);
        cleanups.push(() => observer.disconnect());
        function animate(now) { frame = 0; if (disposed || !visible || document.hidden || state.paused || state.completed)
            return; if (!last)
            last = now; const dt = Math.min((now - last) / 1000, .08); if (dt >= 1 / 30) {
            last = now;
            tick(dt);
            draw();
        } schedule(); }
        function schedule() { if (!disposed && !frame && visible && !document.hidden && !state.paused && !state.completed)
            frame = requestAnimationFrame(animate); }
        function toggleMotion() { state.paused = !state.paused; last = 0; sync(); if (state.paused) {
            say('움직임을 껐어요. 분석은 계속 진행돼요.');
            if (frame)
                cancelAnimationFrame(frame);
            frame = 0;
        }
        else {
            say('다시 드라이브를 시작해요.');
            schedule();
        } }
        steerButtons.forEach(b => listen(b, 'click', () => steer(Number(b.dataset.steer))));
        gearButtons.forEach(b => listen(b, 'click', () => setGear(b.dataset.gear)));
        listen(motionButton, 'click', toggleMotion);
        fullscreenButton.hidden = !document.fullscreenEnabled;
        listen(fullscreenButton, 'click', async () => { try {
            if (document.fullscreenElement === media)
                await document.exitFullscreen();
            else
                await media.requestFullscreen();
        }
        catch {
            say('현재 환경에서는 크게 보기를 사용할 수 없어요.');
        } });
        listen(document, 'fullscreenchange', () => { const expanded = document.fullscreenElement === media; fullscreenButton.setAttribute('aria-label', expanded ? '주행 화면 작게 보기' : '주행 화면 크게 보기'); fullscreenButton.setAttribute('aria-pressed', String(expanded)); resize(); });
        listen(document, 'visibilitychange', () => { last = 0; if (document.hidden) {
            if (frame)
                cancelAnimationFrame(frame);
            frame = 0;
        }
        else
            schedule(); });
        listen(reduced, 'change', e => { if (e.matches && !state.paused)
            toggleMotion(); });
        listen(canvas, 'webglcontextlost', e => { e.preventDefault(); dispose(); onUnavailable(); });
        resize();
        sync();
        schedule();
        return dispose;
    }
    catch (error) {
        dispose();
        throw error;
    }
}
