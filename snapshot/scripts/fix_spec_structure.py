import os
import shutil

def merge_directories(src_dir, dst_dir):
    """
    Recursively moves contents from src_dir to dst_dir.
    Overwrites files if they exist in dst_dir.
    Merges directories.
    """
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
        print(f"Created directory: {dst_dir}")
    
    for item in os.listdir(src_dir):
        if item == "__pycache__":
            continue
            
        s = os.path.join(src_dir, item)
        d = os.path.join(dst_dir, item)
        
        if os.path.isdir(s):
            merge_directories(s, d)
        else:
            if os.path.exists(d):
                os.remove(d)
                print(f"Overwriting {d}")
            shutil.move(s, d)
            print(f"Moved {item} -> {dst_dir}")

def main():
    root_dir = os.getcwd()
    # The accidentally nested directory
    nested_root = os.path.join(root_dir, "packages/cascade-spec/cascade-interfaces")
    nested_src = os.path.join(nested_root, "src/cascade")
    
    # The correct destination
    target_dst = os.path.join(root_dir, "packages/cascade-spec/src/cascade")
    
    print(f"Checking for nested structure at: {nested_src}")
    
    if os.path.exists(nested_src):
        print(f"Found nested content. Merging into {target_dst}...")
        try:
            merge_directories(nested_src, target_dst)
            print("Merge successful.")
            
            print(f"Removing source: {nested_root}")
            shutil.rmtree(nested_root)
        except Exception as e:
            print(f"Error during merge: {e}")
            exit(1)
    else:
        print("No nested content found. Directory structure might already be correct.")

if __name__ == "__main__":
    main()