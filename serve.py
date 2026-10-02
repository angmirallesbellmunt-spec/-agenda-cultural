from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
print('Agenda: http://localhost:8000')
ThreadingHTTPServer(('localhost',8000),SimpleHTTPRequestHandler).serve_forever()
