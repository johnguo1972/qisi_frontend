from pathlib import Path


path = Path('/opt/qisi/nginx.conf')
content = path.read_text()
https_pos = content.find('listen 443')
marker = '        location / {'
index = content.find(marker, https_pos)
if index < 0:
    raise SystemExit('HTTPS frontend location marker not found')

if 'location ~ "^/hw/' in content:
    print('NGINX_QR_RULES_ALREADY_PRESENT')
else:
    snippet = '''        # QR code H5 entry points; keep before the SPA fallback location.
        location ~ "^/hw/([ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6})$" {
            return 302 /#/pages/student/scan-entry?code=$1;
        }

        location ~ "^/paper/([ABCDEFGHJKMNPQRSTUVWXYZ23456789]{8})/([ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6})/p([0-9]+)$" {
            return 302 /#/pages/student/scan-entry?student_code=$1&code=$2&page=$3;
        }

'''
    content = content.replace('location ~ ^/hw/([ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6})$ {', 'location ~ "^/hw/([ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6})$" {')
    content = content.replace('location ~ ^/paper/([ABCDEFGHJKMNPQRSTUVWXYZ23456789]{8})/([ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6})/p([0-9]+)$ {', 'location ~ "^/paper/([ABCDEFGHJKMNPQRSTUVWXYZ23456789]{8})/([ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6})/p([0-9]+)$" {')
    path.write_text(content[:index] + snippet + content[index:] if 'location ~ "^/hw/' not in content else content)
    print('NGINX_QR_RULES_ADDED')
