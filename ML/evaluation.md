## Evaluating a Hypothesis
为了检验算法是否过拟合，我们将数据分成训练集和测试集，通常用70%的数据作为训练集，用剩下30%的数据作为测试集。


![train-test](image-19.png)

![train-test2](image-20.png)

通过比较 训练集误差 和 测试集误差，可以发现模型在训练集表现良好，但是无法泛化到新样本中。

### 交叉验证集 cross validation set
将数据分为3个子集：训练集，交叉验证集，测试集

![cv](image-21.png)