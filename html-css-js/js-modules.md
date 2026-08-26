# JavaScript 模块化（import / export）

## 一、为什么需要模块化？

在 ES6（ES2015）之前，JavaScript 没有官方的模块系统，所有脚本共享同一个全局作用域：

```html
<script src="a.js"></script>
<script src="b.js"></script>
```

这带来几个问题：

- **全局变量污染**：不同文件里的同名变量互相覆盖
- **依赖顺序敏感**：`<script>` 标签顺序写错就报错
- **难以维护**：无法清晰表达"这个文件依赖哪个文件"

**ES Module（ESM）** 是 ES6 引入的官方模块化方案，每个文件就是一个独立模块，有自己的作用域，通过 `export` 暴露接口、通过 `import` 引入依赖。

---

## 二、导出（export）

### 1. 命名导出（Named Export）

一个模块可以有**多个**命名导出。

```js
// math.js
export const PI = 3.14159;

export function add(a, b) {
  return a + b;
}

export function multiply(a, b) {
  return a * b;
}
```

也可以先定义、最后统一导出（推荐，一目了然）：

```js
// math.js
const PI = 3.14159;
function add(a, b) { return a + b; }
function multiply(a, b) { return a * b; }

export { PI, add, multiply };
```

导出时可以起别名：

```js
export { add as sum };
```

### 2. 默认导出（Default Export）

一个模块最多只能有**一个**默认导出，通常代表这个模块的"主要功能"。

```js
// User.js
export default class User {
  constructor(name) {
    this.name = name;
  }
  sayHi() {
    console.log(`你好，我是 ${this.name}`);
  }
}
```

也可以导出一个匿名函数或值：

```js
export default function () { /* ... */ }
// 或
export default 42;
```

### 3. 命名导出 vs 默认导出

| 对比项 | 命名导出 | 默认导出 |
|---|---|---|
| 数量 | 任意多个 | 每模块最多 1 个 |
| 导入语法 | `import { 名字 } from '...'` | `import 任意名 from '...'` |
| 名字 | 必须与导出名一致（可用 `as` 改名） | 导入方自由命名 |
| 适用场景 | 工具函数集、常量集 | 模块的主类 / 主函数 |

---

## 三、导入（import）

### 1. 导入命名导出

```js
import { PI, add } from './math.js';

console.log(PI);          // 3.14159
console.log(add(1, 2));   // 3
```

用 `as` 改名（避免重名冲突）：

```js
import { add as sum } from './math.js';
sum(1, 2);
```

### 2. 导入默认导出

```js
import User from './User.js';   // 名字可以任意起

const u = new User('小明');
u.sayHi();
```

### 3. 混合导入（默认 + 命名）

```js
// module.js
export default function main() {}
export const version = '1.0';

// 使用方
import main, { version } from './module.js';
```

### 4. 整体导入为命名空间对象

```js
import * as math from './math.js';

math.add(1, 2);
console.log(math.PI);
```

**如果模块里有默认导出**，它会挂在命名空间对象的 `default` 属性上（因为 `default` 本质就是一个特殊的导出名字）：

```js
import * as loggerModule from './Logger.js';

loggerModule.default.log('通过 .default 访问默认导出');

// 也可以"默认导出 + 命名空间"同时导入（注意没有大括号）：
import Logger, * as loggerModule2 from './Logger.js';
Logger === loggerModule2.default;   // true
```

### 5. 只执行模块、不导入任何绑定

常用于引入有副作用的模块（如初始化代码、polyfill、CSS）：

```js
import './init.js';
```

### 6. 动态导入 import()

静态 `import` 必须写在顶层且路径固定；动态 `import()` 可以在代码运行时按需加载，返回 Promise：

```js
button.addEventListener('click', async () => {
  const { heavyFunction } = await import('./heavy-module.js');
  heavyFunction();
});
```

常用于**代码分割 / 懒加载**，减小首屏体积。

---

## 四、转发导出（re-export）

把别的模块的内容"中转"出去，常用于编写 `index.js` 统一入口：

```js
// utils/index.js
export { add, multiply } from './math.js';
export { formatDate } from './date.js';
export * from './string.js';
export { default as User } from './User.js';
```

使用者只需要：

```js
import { add, formatDate, User } from './utils/index.js';
```

---

## 五、在浏览器中使用

### 1. `<script type="module">`

```html
<script type="module" src="main.js"></script>
<!-- 或内联 -->
<script type="module">
  import { add } from './math.js';
  console.log(add(1, 2));
</script>
```

### 2. 注意要点

- **路径必须带扩展名**：浏览器里要写 `./math.js`，不能像打包工具那样省略 `.js`
- **必须用服务器访问**：`file://` 直接双击打开会因 CORS 被拦截。本地开发可用：
  - VS Code 插件 **Live Server**
  - `npx serve .`
  - `python -m http.server`
- **自动严格模式**：模块代码默认是 `'use strict'`
- **顶层 this 是 undefined**（普通脚本是 window）
- **默认 defer 行为**：模块脚本不会阻塞 HTML 解析，DOM 就绪后执行
- **变量不污染全局**：模块内声明的变量不进 window

---

## 六、ES Module vs CommonJS（Node.js 旧方案）

| 对比项 | ES Module | CommonJS |
|---|---|---|
| 语法 | `import / export` | `require() / module.exports` |
| 加载方式 | **静态**（编译时确定依赖） | **动态**（运行时加载） |
| 加载时机 | 异步（浏览器中） | 同步 |
| 使用环境 | 浏览器原生支持、Node.js（.mjs 或 `"type": "module"`） | Node.js 传统默认 |
| 值绑定 | 导出的是**活绑定**（live binding） | 导出的是值的拷贝 |
| tree-shaking | 支持（静态结构可分析） | 困难 |

```js
// CommonJS 写法（对照了解即可）
// math.js
module.exports = { add: (a, b) => a + b };
// main.js
const { add } = require('./math');
```

---

## 七、常见错误与练习

### 常见错误

```js
// ❌ 1. 命名导出用了默认导入
import add from './math.js';        // math.js 里 add 是命名导出 → 报错

// ❌ 2. 默认导出用了大括号
import { User } from './User.js';   // User.js 里是 default 导出 → 报错
// ✅ 应写：import User from './User.js'

// ❌ 3. 忘了扩展名（浏览器环境）
import { add } from './math';       // 应写 './math.js'

// ❌ 4. import 写在代码块里（静态 import 必须在顶层）
if (ok) { import { add } from './math.js'; }  // 报错，改用 await import()

// ❌ 5. file:// 直接打开模块页面 → CORS 错误，需起本地服务器
```

