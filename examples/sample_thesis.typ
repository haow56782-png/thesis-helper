#import "../templates/bachelor-cn.typ": thesis

#show: thesis.with(
  title-cn: "基于深度学习的图像分类方法研究",
  title-en: "Research on Image Classification Methods Based on Deep Learning",
  author: "王好",
  student-id: "20210042",
  school: "示范大学",
  department: "计算机科学与技术学院",
  major: "计算机科学与技术",
  advisor: "张教授",
  advisor-title: "教授",
  date: "2026 年 5 月",
  abstract-cn: [
    随着深度学习技术的快速发展，图像分类作为计算机视觉领域的核心任务之一，已经在工业、医疗、安防等多个场景中得到广泛应用。本文系统地研究了基于卷积神经网络的图像分类方法，重点探讨了数据增强、迁移学习与模型蒸馏三种关键技术对分类精度的影响。

    本文的主要贡献包括：第一，构建了一个统一的实验框架，可在 CIFAR-10、ImageNet 子集等多个数据集上对不同模型进行公平对比；第二，提出了一种轻量化的特征融合策略，在保持精度的前提下将参数量降低 30%；第三，通过大量消融实验验证了所提方法的有效性。
  ],
  abstract-en: [
    With the rapid development of deep learning, image classification has become one of the core tasks in computer vision and has been widely applied in industrial, medical, and security scenarios. This thesis systematically studies image classification methods based on convolutional neural networks, focusing on three key techniques: data augmentation, transfer learning, and model distillation.

    The main contributions of this thesis include: first, we build a unified experimental framework for fair comparison across CIFAR-10 and ImageNet subsets; second, we propose a lightweight feature fusion strategy that reduces parameters by 30% while preserving accuracy; third, we validate the effectiveness of our methods through extensive ablation studies.
  ],
  keywords-cn: ("深度学习", "图像分类", "卷积神经网络", "迁移学习"),
  keywords-en: ("Deep Learning", "Image Classification", "CNN", "Transfer Learning"),
)

= 绪论

== 研究背景与意义

图像分类是计算机视觉领域最基础也是最重要的任务之一。它的目标是给定一张输入图像，输出该图像所属的类别。早期的图像分类方法主要依赖人工设计的特征，例如 SIFT、HOG 等。这些方法在特定场景下取得了不错的效果，但泛化能力较弱。

随着深度学习的崛起，特别是卷积神经网络（CNN）的成功应用，图像分类的精度有了质的飞跃。从 AlexNet 到 ResNet，再到近年的 Transformer 类模型，图像分类的 SOTA 不断被刷新。

== 国内外研究现状

国内方面，清华、中科院、商汤等机构在图像分类领域做出了重要贡献。国外方面，Google、Meta、OpenAI 等公司主导了大模型时代的视觉研究方向。

== 本文主要工作

本文的主要工作可以概括为三点：

+ 复现并对比了主流图像分类模型；
+ 提出了一种新的特征融合方法；
+ 通过实验验证了方法的有效性。

= 相关理论基础

== 卷积神经网络

卷积神经网络是一种专门为处理网格状数据（如图像）而设计的神经网络结构。它通过卷积、池化、全连接等操作实现特征的层次化提取。

=== 卷积层

卷积层是 CNN 的核心组件。其数学表达式如下：

$ y_(i,j) = sum_(m=0)^(M-1) sum_(n=0)^(N-1) x_(i+m, j+n) dot w_(m,n) + b $

=== 池化层

池化层用于降低特征图的空间分辨率，同时增强模型的平移不变性。

== 迁移学习

迁移学习的核心思想是将在大规模数据集上预训练的模型迁移到目标任务上，从而减少对目标任务标注数据的依赖。

= 方法设计

== 整体框架

本文提出的方法包含三个主要模块：特征提取、特征融合与分类头。

== 特征融合策略

特征融合的目标是将不同层级的特征有效组合，提升分类精度。

= 实验与分析

== 实验设置

数据集：CIFAR-10、ImageNet-100。训练硬件：NVIDIA RTX 4090。

== 主要结果

#figure(
  table(
    columns: 4,
    align: center,
    table.header[模型][参数量(M)][CIFAR-10 Top-1][ImageNet-100 Top-1],
    [ResNet-50],   [25.6], [94.2%], [78.3%],
    [本文方法],    [17.9], [94.5%], [78.6%],
  ),
  caption: [不同模型在两个数据集上的精度对比],
)

实验结果表明，本文方法在参数量减少 30% 的情况下，精度反而略有提升。

= 总结与展望

本文系统地研究了基于深度学习的图像分类方法。未来可以从更高效的网络结构、更强的数据增强等方向进一步优化。

= 参考文献

#set par(first-line-indent: 0em, hanging-indent: 1.5em)
#set text(size: 10.5pt)

[1] LeCun Y, Bengio Y, Hinton G. Deep learning[J]. Nature, 2015, 521(7553): 436–444.

[2] He K, Zhang X, Ren S, et al. Deep residual learning for image recognition[C]//CVPR. 2016: 770–778.

[3] 周志华. 机器学习[M]. 北京: 清华大学出版社, 2016.

= 致谢

感谢导师张教授的悉心指导，感谢实验室同学的帮助与陪伴。
