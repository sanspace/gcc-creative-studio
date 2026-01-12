from google.cloud.aiplatform_v1.types import IndexDatapoint
# Usually Restriction is defined in same file or common
# It's actually in google.cloud.aiplatform_v1.types.index
try:
    from google.cloud.aiplatform_v1.types import Restriction
except ImportError:
    # Try finding it
    import google.cloud.aiplatform_v1.types as t
    if hasattr(t, "Restriction"):
        Restriction = t.Restriction
    else:
        print("Restriction not found in types")
        exit(1)

print("Restriction fields:", Restriction.meta.fields)
# OR use introspection
r = Restriction()
print("Expected fields in __init__:", dir(r))
try:
    r = Restriction(namespace="foo", allow_tokens=["a"])
    print("Accepted allow_tokens")
except Exception as e:
    print(f"Rejected allow_tokens: {e}")

try:
    r = Restriction(namespace="foo", allow_list=["a"])
    print("Accepted allow_list")
except Exception as e:
    print(f"Rejected allow_list: {e}")
