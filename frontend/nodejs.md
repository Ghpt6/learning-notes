```js
// server.js —— 一个最简单的 HTTP 服务器
const http = require('http');

http.createServer((req, res) => {
  res.end('Hello, Node.js!');
}).listen(3000);
```

运行 node server.js,浏览器访问 http://localhost:3000 就能看到输出。