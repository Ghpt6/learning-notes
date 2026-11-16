# 逻辑回归
- 由于逻辑回归 target $y$ 只能为 0 或 1，我们希望模型输出位于 0 与 1 之间。
- Sigmoid function 可以把任意实数输入映射到 0 与 1 之间，从而实现这一点。

![logistic](image-7.png)

## 代价函数

### 损失函数
**loss** 衡量单个样本的预测与 target 之间的差异，用 **cost** 汇总整个训练集上的 loss。

当 y=1 时，损失函数中，预测值 $f_{\vec{w},b}\left(\vec{x}^{(i)}\right)$ 越趋近于1，表明预测的越准确，损失就越小。 趋近于 0，则表示和实际值 1 差距越大，预测越不准确
![cost](image-8.png)

上面的分段定义可以改写为更方便实现的形式： 
$$
\operatorname{loss}(f_{\vec{\mathbf{w}},b}(\mathbf{x}^{(i)}),y^{(i)})
=-y^{(i)}\log\left(f_{\vec{\mathbf{w}},b}(\mathbf{x}^{(i)})\right)
-(1-y^{(i)})\log\left(1-f_{\vec{\mathbf{w}},b}(\mathbf{x}^{(i)})\right)
$$

# 正则化(Regularization)

## 过拟合

- 欠拟合： 训练数据上都无法很好地拟合
- 泛化： 在训练集之外的例子上也能表现良好
- 过拟合：训练集上表现很好，但是在从未见过的新样本上无法泛化

![overfit](image-9.png)

## 解决过拟合
1. 收集更多数据
2. 正则化：让你保留所有的特征（而不是直接丢弃一些特征），但是减少参数的大小