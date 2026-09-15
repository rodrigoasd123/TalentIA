import http.cookiejar
import io
from pathlib import Path
import re
import urllib.parse
import urllib.request

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# 1. Login
data = urllib.parse.urlencode({
    "correo": "admin@talentia.local",
    "contrasena": "TalentIA-Demo-2026!",
}).encode()
opener.open(urllib.request.Request("http://127.0.0.1:8000/login", data=data, method="POST"))

# 2. Get CSRF token
resp = opener.open("http://127.0.0.1:8000/candidatos/importar-cvs")
html = resp.read().decode("utf-8")
csrf_m = re.search(r'name="csrf"\s+value="([^"]+)"', html)
csrf = csrf_m.group(1)

# 3. Subir los 9 primeros CVs
cv_dir = Path("descargas_talento/05_Lote_Pruebas_10_CVs")
archivos = sorted([f for f in cv_dir.glob("*.docx") if not f.name.startswith("10_")])

boundary = "----WebKitFormBoundaryXzTestTalentIA99"
body = io.BytesIO()

def add_field(name, val):
    body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{val}\r\n".encode("utf-8"))

def add_file(field, path):
    content = path.read_bytes()
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode("utf-8"))
    body.write(content)
    body.write(b"\r\n")

add_field("csrf", csrf)
add_field("cliente_id", "f2734041fc0540b4b01f4415086005ae")
add_field("fuente", "Lote de Pruebas")
add_field("reclutador", "admin@talentia.local")

for fpath in archivos:
    add_file("archivos", fpath)
body.write(f"--{boundary}--\r\n".encode("utf-8"))

req = urllib.request.Request(
    "http://127.0.0.1:8000/candidatos/importar-cvs",
    data=body.getvalue(),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
resp = opener.open(req)
html_resp = resp.read().decode("utf-8")

print("Status Carga Masiva (9 CVs):", resp.status)
print("Contiene Alertas TCS:")
print("  - Excolaborador elegible:", "excolaborador TCS elegible" in html_resp)
print("  - Excolaborador NO elegible:", "excolaborador TCS no elegible" in html_resp)
print("  - Restriccion vigente / Vetado:", "restriccion vigente" in html_resp or "restricción vigente" in html_resp)

# 4. Ahora subir el CV 10 (Duplicado de Gonzalo Benavides) para probar reutilización
body2 = io.BytesIO()
add_field_2 = lambda n, v: body2.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode("utf-8"))
add_field_2("csrf", csrf)
add_field_2("cliente_id", "f2734041fc0540b4b01f4415086005ae")
cv10_path = cv_dir / "10_CV_Duplicado_Gonzalo_Benavides.docx"
content10 = cv10_path.read_bytes()
body2.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"archivos\"; filename=\"{cv10_path.name}\"\r\nContent-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n".encode("utf-8"))
body2.write(content10)
body2.write(b"\r\n")
body2.write(f"--{boundary}--\r\n".encode("utf-8"))

req2 = urllib.request.Request(
    "http://127.0.0.1:8000/candidatos/importar-cvs",
    data=body2.getvalue(),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
resp2 = opener.open(req2)
html_resp2 = resp2.read().decode("utf-8")
print("\nStatus Carga CV 10 (Duplicado):", resp2.status)
print("  - Identidad Reutilizada (sin duplicar ficha):", "reutilizado" in html_resp2)

print("\nFilas en la respuesta del CV 10:")
for row in re.findall(r"<tr>(.*?)</tr>", html_resp2, re.DOTALL):
    cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td.*?>(.*?)</td>", row, re.DOTALL)]
    if cells:
        print(" ", " | ".join(cells))

