from collections import defaultdict, deque

user_memory = defaultdict(lambda: deque(maxlen=3))

def store_checkin(user_id, data):
    user_memory[user_id].append(data)

def get_user_history(user_id):
    return list(user_memory[user_id])
