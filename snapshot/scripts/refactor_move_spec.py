import shutil
import os
import sys

def main():
    print("Starting refactor: extracting cascade-spec...")
    
    # Paths
    root_dir = os.getcwd()
    pkg_interfaces = os.path.join(root_dir, "packages/cascade-interfaces")
    pkg_spec = os.path.join(root_dir, "packages/cascade-spec")
    
    # 1. Create cascade-spec from interfaces
    if os.path.exists(pkg_spec):
        print(f"Warning: {pkg_spec} already exists. Skipping copy.")
    else:
        if os.path.exists(pkg_interfaces):
            print(f"Copying {pkg_interfaces} to {pkg_spec}...")
            shutil.copytree(pkg_interfaces, pkg_spec)
        else:
            print(f"Error: Source {pkg_interfaces} not found.")
            sys.exit(1)

    # 2. Move Blueprint from Runtime to Spec
    # Source: packages/cascade-runtime/src/cascade/runtime/blueprint.py
    # Dest: packages/cascade-spec/src/cascade/spec/blueprint.py
    src_bp = os.path.join(root_dir, "packages/cascade-runtime/src/cascade/runtime/blueprint.py")
    dst_bp = os.path.join(pkg_spec, "src/cascade/spec/blueprint.py")
    
    if os.path.exists(src_bp):
        print(f"Moving {src_bp} to {dst_bp}...")
        # Ensure dest directory exists
        os.makedirs(os.path.dirname(dst_bp), exist_ok=True)
        shutil.move(src_bp, dst_bp)
    else:
        print(f"Warning: Source blueprint {src_bp} not found (maybe already moved?).")

    # 3. Move Graph Model to Spec Model
    # Source: packages/cascade-spec/src/cascade/graph/model.py
    # Dest: packages/cascade-spec/src/cascade/spec/model.py
    src_model = os.path.join(pkg_spec, "src/cascade/graph/model.py")
    dst_model = os.path.join(pkg_spec, "src/cascade/spec/model.py")
    
    if os.path.exists(src_model):
        print(f"Moving {src_model} to {dst_model}...")
        shutil.move(src_model, dst_model)
        # Clean up empty graph dir if it exists
        graph_dir = os.path.dirname(src_model)
        if os.path.exists(graph_dir) and not os.listdir(graph_dir):
            os.rmdir(graph_dir)
            print(f"Removed empty directory {graph_dir}")

    # 4. Update pyproject.toml in cascade-spec
    spec_toml = os.path.join(pkg_spec, "pyproject.toml")
    if os.path.exists(spec_toml):
        with open(spec_toml, "r") as f:
            content = f.read()
        
        content = content.replace('name = "cascade-interfaces"', 'name = "cascade-spec"')
        content = content.replace(
            'description = "Interfaces, specifications, and data models for the Cascade ecosystem."', 
            'description = "Core specifications, data models, and contracts for the Cascade ecosystem."'
        )
        
        with open(spec_toml, "w") as f:
            f.write(content)
        print("Updated cascade-spec/pyproject.toml")

    # 5. Global Search and Replace
    replacements = {
        "cascade-interfaces": "cascade-spec",
        "cascade.runtime.blueprint": "cascade.spec.blueprint",
        "cascade.graph.model": "cascade.spec.model",
    }
    
    print("Performing global text replacements...")
    for root, dirs, files in os.walk(root_dir):
        # Skip hidden/system dirs and the script itself if in loop
        if any(p.startswith(".") for p in root.split(os.sep)) or "venv" in root or "__pycache__" in root:
            continue
            
        for file in files:
            if file.endswith((".py", ".toml")):
                path = os.path.join(root, file)
                # Skip the file we are currently running if possible, though it's in scripts/
                if path == __file__:
                    continue

                try:
                    with open(path, "r") as f:
                        old_content = f.read()
                    
                    new_content = old_content
                    for old, new in replacements.items():
                        new_content = new_content.replace(old, new)
                    
                    if new_content != old_content:
                        print(f"Patching {path}...")
                        with open(path, "w") as f:
                            f.write(new_content)
                except Exception as e:
                    print(f"Failed to process {path}: {e}")

    # 6. Remove old interfaces package
    if os.path.exists(pkg_interfaces):
        print(f"Removing old package {pkg_interfaces}...")
        shutil.rmtree(pkg_interfaces)
    
    print("Refactor complete.")

if __name__ == "__main__":
    main()