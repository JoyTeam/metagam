import json

class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        return None
