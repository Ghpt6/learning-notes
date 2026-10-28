## 向量和矩阵
向量有两种最基本的运算: 
- **相加：对应分量相加。** 几何上，可以理解为连续走两段路。
- **乘一个数：每个分量都乘这个数。** 几何上，就是拉长、缩短；乘负数还会反向。
例如：

\[
\begin{pmatrix}1\\2\end{pmatrix}
+
\begin{pmatrix}3\\1\end{pmatrix}
=
\begin{pmatrix}4\\3\end{pmatrix},
\qquad
2\begin{pmatrix}1\\2\end{pmatrix}
=
\begin{pmatrix}2\\4\end{pmatrix}
\]

### 线性组合
把“乘数”和“相加”结合起来，就得到一个很重要的概念：线性组合。例如 \(2\mathbf u+3\mathbf v\)，就是取两份 \(\mathbf u\)、三份 \(\mathbf v\)，再加起来。

## 矩阵运算
按行计算各个输出分量，按列理解输入怎样组合出输出

行计算：

\[
A\mathbf v
=
\begin{pmatrix}2&1\\0&1\end{pmatrix}
\begin{pmatrix}1\\2\end{pmatrix}
=
\begin{pmatrix}
2\times1+1\times2\\
0\times1+1\times2
\end{pmatrix}
=
\begin{pmatrix}4\\2\end{pmatrix}
\]

列：  

\[
A\mathbf v
=
1\begin{pmatrix}2\\0\end{pmatrix}
+
2\begin{pmatrix}1\\1\end{pmatrix}
=
\begin{pmatrix}4\\2\end{pmatrix}
\]

### 矩阵乘法
假设有一个矩阵,如果先用 \(B\)，再用 \(A\)，整个过程就是：
\[
\mathbf v
\;\longrightarrow\;
B\mathbf v
\;\longrightarrow\;
A(B\mathbf v)
\]

我们希望把这两个连续变换合成一个矩阵，于是定义乘积 \(AB\)，让它满足：
\[
(AB)\mathbf v=A(B\mathbf v)
\]

**矩阵乘法的一个核心意义，就是把连续的线性变换合成一次变换。**
计算规则是：左矩阵的一行，与右矩阵的一列，对应相乘再相加。

\[
AB=
\begin{pmatrix}2&1\\0&1\end{pmatrix}
\begin{pmatrix}0&-1\\1&0\end{pmatrix}
=
\begin{pmatrix}1&-2\\1&0\end{pmatrix}
\]

为什么这种规则能表示连续变换？因为 \(B\) 的每一列记录了一个**基本方向**经过 \(B\) 后的结果；再让 \(A\) 作用于这些列，就得到了连续变换后的结果。


顺序通常会影响答案。对我们一直使用的 \(\mathbf v=(1,2)\)：
| 顺序 | 中间结果 | 最终结果 |
|---|---|---|
| 先 \(B\)，再 \(A\) | \((-2,1)\) | \((-3,1)\) |
| 先 \(A\)，再 \(B\) | \((4,2)\) | \((-2,4)\) |


因此，这里 \(AB\ne BA\)。矩阵乘法一般不能随意交换顺序。
## 矩阵的秩和行列式
- 秩：变换后的所有可能输出，需要几个独立方向才能描述？
- 行列式：变换使面积或体积缩放了多少倍，是否翻转了方向？

取一个面积为 1 的单位正方形，让矩阵作用于它的每一个点。在二维线性变换下，它通常会变成一个平行四边形，也可能被压成线段或点。
**变换后的面积，是行列式的绝对值。**

## 特征值和特征向量
特征向量，是矩阵作用后仍落在原来那条直线上的非零向量；
特征值，是它被乘上的那个数。

\[
A\mathbf v=\lambda\mathbf v
\]