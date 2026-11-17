from pathlib import Path
import json
import pymeshlab
root=Path(__file__).parent/'final'
results={}
for path in root.glob('*.stl'):
    meshes=pymeshlab.MeshSet()
    meshes.load_new_mesh(str(path))
    meshes.apply_filter('compute_selection_by_self_intersections_per_face')
    results[path.name]=meshes.current_mesh().selected_face_number()
(root/'self_intersections.json').write_text(json.dumps(results,indent=2))
assert not any(results.values()), results
print(results)
