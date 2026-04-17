def get_status_color(status):
    colors = {
        'pass': '#28a745',   # Green
        'warn': '#ffc107',   # Yellow/Orange
        'fail': '#dc3545'    # Red
    }
    return colors.get(status, '#6c757d')

def get_status_emoji(status):
    emojis = {
        'pass': '✅',
        'warn': '⚠️',
        'fail': '🔴'
    }
    return emojis.get(status, 'ℹ️')