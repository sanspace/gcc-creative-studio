from google.cloud.aiplatform_v1.types import IndexDatapoint
import inspect

print("IndexDatapoint found.")
# Create dummy
try:
    idp = IndexDatapoint()
    print("IndexDatapoint created.")
    # Inspect 'restricts' field
    # In proto-plus, repeated fields are list-like
    print(f"Restricts type: {type(idp.restricts)}")
    # We can try to append a dict
    try:
        idp.restricts.append({"namespace": "test", "allow_list": ["a"]})
        print("Accepted dict with allow_list")
    except Exception as e:
        print(f"Rejected dict with allow_list: {e}")
        
    try:
        idp.restricts.append({"namespace": "test", "allow_tokens": ["a"]})
        print("Accepted dict with allow_tokens")
    except Exception as e:
        print(f"Rejected dict with allow_tokens: {e}")

except Exception as e:
    print(f"Error: {e}")
