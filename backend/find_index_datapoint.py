import google.cloud.aiplatform
import inspect

print("Searching for IndexDatapoint...")

def search_module(module, name, path=""):
    try:
        if hasattr(module, name):
            print(f"FOUND: {path}.{name}")
    except:
        pass

    # Try common submodules
    submodules = ["matching_engine", "gapic", "v1", "aiplatform_v1"]
    for sub in submodules:
        try:
            m = getattr(module, sub, None)
            if m:
                if hasattr(m, name):
                    print(f"FOUND: {path}.{sub}.{name}")
                # Go one level deeper for types
                if hasattr(m, "types"):
                    if hasattr(m.types, name):
                        print(f"FOUND: {path}.{sub}.types.{name}")
        except Exception as e:
            print(f"Error checking {sub}: {e}")

try:
    from google.cloud import aiplatform_v1
    if hasattr(aiplatform_v1, "IndexDatapoint"):
         print("FOUND: google.cloud.aiplatform_v1.IndexDatapoint")
    if hasattr(aiplatform_v1.types, "IndexDatapoint"):
         print("FOUND: google.cloud.aiplatform_v1.types.IndexDatapoint")
except ImportError:
    print("Could not import aiplatform_v1")

search_module(google.cloud.aiplatform, "IndexDatapoint", "google.cloud.aiplatform")
