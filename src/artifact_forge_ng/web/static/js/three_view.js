// 3D lens: STL artifacts + region boxes, and assemblies placed by the
// poses the pipeline REPORTED (assembly_pose) — never re-derived here.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

const ROLE_COLORS = {
  mounting_surface: 0xd9b544, fastener_keepout: 0xe05575,
  soft_contact_surface: 0x4dc3d6, high_stress_region: 0xf0a832,
  retaining_flexure: 0x46c07a, aesthetic_lightening: 0x8a93a3,
  seal_surface: 0xa06be0,
  exoskeleton_panel: 0x6bd06b, rib_anchor: 0xc9963c,
  interface_keepout: 0xd05555,
};

export class ThreeView {
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0d0f12);
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    container.appendChild(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 1.1);
    key.position.set(1, -1.4, 1.8);
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0x4dc3d6, 0.25);
    rim.position.set(-1.5, 1, 0.5);
    this.scene.add(rim);
    this.grid = new THREE.GridHelper(400, 40, 0x233040, 0x1a212b);
    this.grid.rotation.x = Math.PI / 2; // engine Z-up: grid on XY plane
    this.scene.add(this.grid);
    this.meshes = new THREE.Group();
    this.regionGroup = new THREE.Group();
    this.scene.add(this.meshes, this.regionGroup);
    this._resize = () => {
      const w = container.clientWidth || 600, h = container.clientHeight || 400;
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
    };
    new ResizeObserver(this._resize).observe(container);
    this._resize();
    const loop = () => {
      requestAnimationFrame(loop);
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    };
    loop();
  }

  clear() {
    for (const g of [this.meshes, this.regionGroup]) {
      while (g.children.length) g.remove(g.children[0]);
    }
  }

  async loadSTL(url, pose = null, tint = 0xb9c2cf) {
    const loader = new STLLoader();
    const geo = await new Promise((res, rej) => loader.load(url, res, undefined, rej));
    geo.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({
      color: tint, metalness: 0.15, roughness: 0.55,
    });
    const mesh = new THREE.Mesh(geo, mat);
    if (pose) {
      // quarter-turn Euler XYZ + translate, exactly as reported
      const [rx, ry, rz] = (pose.rotate || [0, 0, 0]).map((d) => (d * Math.PI) / 180);
      mesh.rotation.set(rx, ry, rz, "XYZ");
      const [tx, ty, tz] = pose.translate || [0, 0, 0];
      mesh.position.set(tx, ty, tz);
    }
    this.meshes.add(mesh);
    return mesh;
  }

  showRegions(regions, visible = true) {
    while (this.regionGroup.children.length)
      this.regionGroup.remove(this.regionGroup.children[0]);
    if (!visible || !regions) return;
    for (const r of regions) {
      const b = r.box;
      const sx = Math.max(b.x1 - b.x0, 0.4), sy = Math.max(b.y1 - b.y0, 0.4),
        sz = Math.max(b.z1 - b.z0, 0.4);
      const geo = new THREE.BoxGeometry(sx, sy, sz);
      const mat = new THREE.MeshBasicMaterial({
        color: ROLE_COLORS[r.role] ?? 0x8a93a3,
        transparent: true, opacity: 0.16, depthWrite: false,
      });
      const box = new THREE.Mesh(geo, mat);
      box.position.set((b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2, (b.z0 + b.z1) / 2);
      box.userData.region = r;
      const edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(geo),
        new THREE.LineBasicMaterial({
          color: ROLE_COLORS[r.role] ?? 0x8a93a3, transparent: true, opacity: 0.6,
        })
      );
      box.add(edges);
      this.regionGroup.add(box);
    }
  }

  // Click → region (raycast over the region boxes). A short-move guard
  // keeps orbit drags from counting as picks.
  enableRegionPicking(onPick) {
    const ray = new THREE.Raycaster();
    const ptr = new THREE.Vector2();
    let down = null;
    const el = this.renderer.domElement;
    el.addEventListener("pointerdown", (ev) => { down = [ev.clientX, ev.clientY]; });
    el.addEventListener("click", (ev) => {
      if (down && Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) > 5) return;
      const rect = el.getBoundingClientRect();
      ptr.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      ptr.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      ray.setFromCamera(ptr, this.camera);
      const hits = ray.intersectObjects(this.regionGroup.children, false);
      if (hits.length) onPick(hits[0].object.userData.region);
    });
  }

  // Selected region turns amber and opaque; with a selection active the
  // rest fade to ghosts AND the part itself goes translucent, so the
  // region reads as "this zone of the part", not an abstract floating box.
  highlightRegion(name) {
    for (const box of this.regionGroup.children) {
      const r = box.userData.region;
      const on = !!name && r?.name === name;
      const base = ROLE_COLORS[r?.role] ?? 0x8a93a3;
      box.material.color.set(on ? 0xffc94d : base);
      box.material.opacity = on ? 0.45 : name ? 0.03 : 0.16;
      box.scale.setScalar(on ? 1.02 : 1.0);
      const edges = box.children[0];
      if (edges) {
        edges.material.color.set(on ? 0xffd76a : base);
        edges.material.opacity = on ? 1.0 : name ? 0.12 : 0.6;
      }
    }
    for (const mesh of this.meshes.children) {
      mesh.material.transparent = true;
      mesh.material.opacity = name ? 0.5 : 1.0;
      mesh.material.depthWrite = !name;
      mesh.material.needsUpdate = true;
    }
  }

  fit() {
    let box = new THREE.Box3().setFromObject(this.meshes);
    if (box.isEmpty()) box = new THREE.Box3().setFromObject(this.regionGroup);
    if (box.isEmpty()) return;
    const size = box.getSize(new THREE.Vector3()).length() || 100;
    const center = box.getCenter(new THREE.Vector3());
    this.camera.up.set(0, 0, 1); // engine frame: Z up
    this.camera.position.set(
      center.x + size * 0.7, center.y - size * 0.9, center.z + size * 0.6
    );
    this.controls.target.copy(center);
    this.camera.near = size / 100;
    this.camera.far = size * 10;
    this.camera.updateProjectionMatrix();
    this.grid.position.set(center.x, center.y, 0);
  }
}
