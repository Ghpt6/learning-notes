const http = require('http');

http.createServer((req, res) => {
  res.end('Hello, Node.js!');
}).listen(3000);