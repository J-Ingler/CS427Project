import http.server
import socketserver

PORT = 8000

class MyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.path = "/index.html"  # Serve index.html by default
        try:
            with open(self.path) as file:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(bytes(file.read(), "utf-8"))
        except FileNotFoundError:
            self.send_error(404, "File Not Found")

with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
    print("Serving on port", PORT)
    httpd.serve_forever()