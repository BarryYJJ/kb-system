# mHC: Manifold-Constrained Hyper-Connections (DeepSeek)

**来源**: DeepSeek-AI, arXiv:2512.24880, 2025-12

**类型**: text

**入库时间**: 2026-03-17T08:27:00.144425

---

mHC: Manifold-Constrained Hyper-Connections
Zhenda Xie*†, Yixuan Wei*, Huanqi Cao*,
Chenggang Zhao, Chengqi Deng, Jiashi Li, Damai Dai, Huazuo Gao, Jiang Chang,
Kuai Yu, Liang Zhao, Shangyan Zhou, Zhean Xu, Zhengyan Zhang, Wangding Zeng,
Shengding Hu, Yuqing Wang, Jingyang Yuan, Lean Wang, Wenfeng Liang
DeepSeek-AI
Abstract
Recently, studies exemplified by Hyper-Connections (HC) have extended the ubiquitous resid-
ual connection paradigm established over the past decade by expanding the residual stream
width and diversifying connectivity patterns. While yielding substantial performance gains,
this diversification fundamentally compromises the identity mapping property intrinsic to
the residual connection, which causes severe training instability and restricted scalability, and
additionally incurs notable memory access overhead. To address these challenges, we pro-
poseManifold-Constrained Hyper-Connections(mHC), a general framework that projects
the residual connection space of HC onto a specific manifold to restore the identity mapping
property, while incorporating rigorous infrastructure optimization to ensure efficiency. Em-
pirical experiments demonstrate thatmHC is effective for training at scale, offering tangible
performance improvements and superior scalability. We anticipate thatmHC, as a flexible and
practical extension of HC, will contribute to a deeper understanding of topological architecture
design and suggest promising directions for the evolution of foundational models.
(a) Residual Connection(b) Hyper-Connections(HC)(c) Manifold-Constrained HC (mHC)Layerℱ
x!x!"#
Res Mappingℋ!$%&Pre Mappingℋ!'$%Post Mappingℋ!'(&)Layer ℱx!"#
h!$%&x!h!'(&)
h!*+h!(,)
Res Mapping𝒫ℳ!"#(ℋ!$%&)Pre Mapping𝒫ℳ$!"(ℋ!'$%)Post Mapping𝒫ℳ$%#&(ℋ!'(&))Layer ℱx!"#
h!$%&x!h!'(&)
h!*+h!(,)
Figure 1|Illustrations of Residual Connection Paradigms.This figure compares the structural
design of (a) standard Residual Connection, (b) Hyper-Connections (HC), and (c) our proposed
Manifold-Constrained Hyper-Connections(mHC). Unlike the unconstrained HC,mHC focuses
on optimizing the residual connection space by projecting the matrices onto a constrained
manifold to ensure stability.
*Core contributors.†Corresponding author: xie.zhenda@deepseek.comarXiv:2512.24880v2  [cs.CL]  5 Jan 2026Contents
1 Introduction 3
2 Related Works 4
2.1 Micro Design . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 4
2.2 Macro Design . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 5
3 Preliminary 5
3.1 Numerical Instability . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 6
3.2 System Overhead . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 7
4 Method 8
4.1 Manifold-Constrained Hyper-Connections . . . . . . . . . . . . . . . . . . . . . . 8
4.2 Parameterization and Manifold Projection . . . . . . . . . . . . . . . . . . . . . . . 9
4.3 Efficient Infrastructure Design . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 9
4.3.1 Kernel Fusion . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 9
4.3.2 Recomputing . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 10
4.3.3 Overlapping Communication in DualPipe . . . . . . . . . . . . . . . . . . 11
5 Experiments 12
5.1 Experimental Setup . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 12
5.2 Main Results . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 12
5.3 Scaling Experiments . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 13
5.4 Stability Analysis . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 14
6 Conclusion and Outlook 15
A Appendix 19
A.1 Detailed Model Specifications and Hyper-parameters. . . . . . . . . . . . . . . . . 19
21. Introduction
Deep neural network architectures have undergone rapid evolution since the introduction of
ResNets (He et al., 2016a). As illustrated in Fig. 1(a), the structure of a single-layer can be
formulated as follows:
x𝑙+1=x𝑙+F(x𝑙,W𝑙), (1)
wherex 𝑙andx𝑙+1denote the 𝐶-dimensional input and output of the 𝑙-th layer, respectively,
andFrepresents the residual function. Although the residual function Fhas evolved over
the past decade to include various operations such as convolution, attention mechanisms, and
feed forward networks, the paradigm of the residual connection has maintained its original
form. Accompanying the progression of Transformer (Vaswani et al., 2017) architecture, this
paradigm has currently established itself as a fundamental design element in large language
models (LLMs) (Brown et al., 2020; Liu et al., 2024b; Touvron et al., 2023).
This success is primarily attributed to the concise form of the residual connection. More
importantly, early research (He et al., 2016b) revealed that the identity mapping property of the
residual connection maintains stability and efficiency during large-scale training. By recursively
extending the residual connection across multiple layers, Eq. (1) yields:
x𝐿=x𝑙+𝐿−1∑︁
𝑖=𝑙F(x𝑖,W𝑖), (2)
where𝐿and𝑙correspond to deeper and shallower layers, respectively. The term identity
mapping refers to the componentx 𝑙itself, which emphasizes the property that the signal from
the shallower layer maps directly to the deeper layer without any modification.
Recently, studies exemplified by Hyper-Connections (HC) (Zhu et al., 2024) have introduced
a new dimension to the residual connection and empirically demonstrated its performance
potential. The single-layer architecture of HC is illustrated in Fig. 1(b). By expanding the width of
the residual stream and enhancing connection complexity, HC significantly increases topological
complexity without altering the computational overhead of individual units regarding FLOPs.
Formally, single-layer propagation in HC is defined as:
x𝑙+1=Hres
𝑙x𝑙+Hpost⊤
𝑙F(Hpre
𝑙x𝑙,W𝑙), (3)
wherex 𝑙andx𝑙+1denote the input and output of the 𝑙-th layer, respectively. Unlike the formu-
lation in Eq. (1), the feature dimension ofx 𝑙andx𝑙+1is expanded from 𝐶to𝑛×𝐶 , where𝑛is
the expansion rate. The term Hres
𝑙∈R𝑛×𝑛represents a learnable mapping that mixes features
within the residual stream. Also as a learnable mapping, Hpre
𝑙∈R1×𝑛aggregates features from
the𝑛𝐶-dim stream into a 𝐶-dim layer input, and conversely, Hpost
𝑙∈R1×𝑛maps the layer output
back onto the stream.
However, as the training scale increases, HC introduces potential risks of instability. The
primary concern is that the unconstrained nature of HC compromises the identity mapping
property when the architecture extends across multiple layers. In architectures comprising
multiple parallel streams, an ideal identity mapping serves as a conservation mechanism. It
ensures that the average signal intensity across streams remains invariant during both forward
and backward propagation. Recursively extending HC to multiple layers via Eq. (3) yields:
x𝐿= 𝐿−𝑙Ö
𝑖=1Hres
𝐿−𝑖!
x𝑙+𝐿−1∑︁
𝑖=𝑙©­
«𝐿−1−𝑖Ö
𝑗=1Hres
𝐿−𝑗ª®
¬Hpost⊤
𝑖F(Hpre
𝑖x𝑖,W𝑖), (4)
3where𝐿and𝑙represent a deeper layer and a shallower layer, respectively. In contrast to Eq. (2),
the composite mappingÎ𝐿−𝑙
𝑖=1Hres
𝐿−𝑖in HC fails to preserve the global mean of the features. This
discrepancy leads to unbounded signal amplification or attenuation, resulting in instability
during large-scale training. A further consideration is that, while HC preserves computational
efficiency in terms of FLOPs, the hardware efficiency concerning memory access costs for the
widened residual stream remains unaddressed in the original design. These factors collectively
restrict the practical scalability of HC and hinder its application in large-scale training.
To address these challenges, we proposeManifold-Constrained Hyper-Connections(mHC),
as shown in Fig. 1(c), a general framework that projects the residual connection space of HC
onto a specific manifold to restore the identity mapping property, while incorporating rigorous
infrastructure optimization to ensure efficiency. Specifically,mHC utilizes the Sinkhorn-Knopp
algorithm (Sinkhorn and Knopp, 1967) to entropically project Hres
𝑙onto the Birkhoff polytope.
This operation effectively constrains the residual connection matrices within the manifold
that is constituted by doubly stochastic matrices. Since the row and column sums of these
matrices equal to 1, the operation Hres
𝑙x𝑙functions as a convex combination of the input features.
This characteristic facilitates a well-conditioned signal propagation where the feature mean
is conserved, and the signal norm is strictly regularized, effectively mitigating the risk of
vanishing or exploding signals. Furthermore, due to the closure of matrix multiplication for
doubly stochastic matrices, the composite mappingÎ𝐿−𝑙
𝑖=1Hres
𝐿−𝑖retains this conservation property.
Consequently,mHC effectively maintains the stability of identity mappings between arbitrary
depths. To ensure efficiency, we employ kernel fusion and develop mixed precision kernels
utilizing TileLang (Wang et al., 2025). Furthermore, we mitigate the memory footprint through
selective recomputing and carefully overlap communication within the DualPipe schedule (Liu
et al., 2024b).
Extensive experiments on language model pretraining demonstrate thatmHC exhibits
exceptional stability and scalability while maintaining the performance advantages of HC. In-
house large-scale training indicates thatmHC supports training at scale and introduces only a
6.7% additional time overhead when expansion rate𝑛=4.
2. Related Works
Architectural advancements in deep learning can be primarily classified intomicro-designand
macro-design. Micro-design concerns the internal architecture of computational blocks, specifying
how features are processed across spatial, temporal, and channel dimensions. In contrast,
macro-design establishes the inter-block topological structure, thereby dictating how feature
representations are propagated, routed, and merged across distinct layers.
2.1. Micro Design
Driven by parameter sharing and translation invariance, convolution initially dominated the pro-
cessing of structured signals. While subsequent variations such as depthwise separable (Chollet,
2017) and grouped convolutions (Xie et al., 2017) optimized efficiency, the advent of Trans-
formers (Vaswani et al., 2017) established Attention and Feed-Forward Networks (FFNs) as
the fundamental building blocks of modern architecture. Attention mechanisms facilitate
global information propagation, while FFNs enhance the representational capacity of individual
features. To balance performance with the computational demands of LLMs, attention mecha-
nisms have evolved towards efficient variants such as Multi-Query Attention (MQA) (Shazeer,
2019), Grouped-Query Attention (GQA) (Ainslie et al., 2023), and Multi-Head Latent Attention
4(MLA) (Liu et al., 2024a). Simultaneously, FFNs have been generalized into sparse computing
paradigms via Mixture-of-Experts (MoE) (Fedus et al., 2022; Lepikhin et al., 2020; Shazeer et al.,
2017), allowing for massive parameter scaling without proportional computational costs.
2.2. Macro Design
Macro-design governs the global topology of the network (Srivastava et al., 2015). Following
ResNet (He et al., 2016a), architectures such as DenseNet (Huang et al., 2017) and Fractal-
Net (Larsson et al., 2016) aimed to enhance performance by increasing topological complexity
through dense connectivity and multi-path structures, respectively. Deep Layer Aggregation
(DLA) (Yu et al., 2018) further extended this paradigm by recursively aggregating features across
various depths and resolutions.
More recently, the focus of macro-design has shifted toward expanding the width of the
residual stream (Chai et al., 2020; Fang et al., 2023; Heddes et al., 2025; Mak and Flanigan,
2025; Menghani et al., 2025; Pagliardini et al., 2024; Xiao et al., 2025; Xie et al., 2023; Zhu et al.,
2024). Hyper-Connections (HC) (Zhu et al., 2024) introduced learnable matrices to modulate
connection strengths among features at varying depths, while the Residual Matrix Transformer
(RMT) (Mak and Flanigan, 2025) replaced the standard residual stream with an outer-product
memory matrix to facilitate feature storage. Similarly, MUDDFormer (Xiao et al., 2025) employs
multiway dynamic dense connections to optimize cross-layer information flow. Despite their
potential, these approaches compromise the inherent identity mapping property of the residual
connection, thereby introducing instability and hindering scalability. Furthermore, they incur
significant memory access overhead due to expanded feature widths. Building upon HC,
the proposedmHC restricts the residual connection space onto a specific manifold to restore
the identity mapping property, while also incorporating rigorous infrastructure optimizations
to ensure efficiency. This approach enhances stability and scalability while maintaining the
topological benefits of expanded connections.
3. Preliminary
We first establish the notation used in this work. In the HC formulation, the input to the 𝑙-th layer,
x𝑙∈R1×𝐶, is expanded by a factor of 𝑛to construct a hidden matrix x𝑙=(x⊤
𝑙,0,...,x⊤
𝑙,𝑛−1)⊤∈R𝑛×𝐶
which can be viewed as 𝑛-stream residual. This operation effectively broadens the width of
the residual stream. To govern the read-out, write-in, and updating processes of this stream,
HC introduces three learnable linear mappings— Hpre
𝑙,Hpost
𝑙∈R1×𝑛, andHres
𝑙∈R𝑛×𝑛. These
mappings modify the standard residual connection shown in Eq. (1), resulting in the formulation
given in Eq. (3).
In the HC formulation, learnable mappings are composed of two parts of coefficients: the
input-dependent one and the global one, referred to as dynamic mappings and static mappings,
respectively. Formally, HC computes the coefficients as follows:
 
˜x𝑙=RMSNorm(x 𝑙)
Hpre
𝑙=𝛼pre
𝑙·tanh(𝜃pre
𝑙˜x⊤
𝑙)+bpre
𝑙
Hpost
𝑙=𝛼post
𝑙·tanh(𝜃post
𝑙˜x⊤
𝑙)+bpost
𝑙
Hres
𝑙=𝛼res
𝑙·tanh(𝜃res
𝑙˜x⊤
𝑙)+bres
𝑙,(5)
where RMSNorm(·) (Zhang and Sennrich, 2019) is applied to the last dimension, and the scalars
𝛼pre
𝑙,𝛼post
𝑙and𝛼res
𝑙∈R are learnable gating factors initialized to small values. The dynamic
5mappings are derived via linear projections parameterized by 𝜃pre
𝑙,𝜃post
𝑙∈R1×𝐶and𝜃res
𝑙∈R𝑛×𝐶,
while the static mappings are represented by learnable biasesbpre
𝑙,bpost
𝑙∈R1×𝑛andbres
𝑙∈R𝑛×𝑛.
It is worth noting that the introduction of these mappings— Hpre
𝑙,Hpost
𝑙, andHres
𝑙—incurs
negligible computational overhead, as the typical expansion rate 𝑛, e.g. 4, is much smaller than
the input dimension 𝐶. With this design, HC effectively decouples the information capacity
of the residual stream from the layer’s input dimension, which is strongly correlated with the
model’s computational complexity (FLOPs). Consequently, HC offers a new avenue for scaling
by adjusting the residual stream width, complementing the traditional scaling dimensions of
model FLOPs and training data size discussed in pre-training scaling laws (Hoffmann et al.,
2022).
Although HC necessitates three mappings to manage the dimensional mismatch between
the residual stream and the layer input, preliminary experiments presented in Tab. 1 indicate
that the residual mapping Hres
𝑙yields the most significant performance gain. This finding
underscores the critical importance of effective information exchange within the residual stream.
Table 1|Ablation Study of HC Components.When a specific mapping ( Hpre
𝑙,Hpost
𝑙, orHres
𝑙) is
disabled, we employ a fixed mapping to maintain dimensional consistency: uniform weights of
1/𝑛forHpre
𝑙, uniform weights of ones forHpost
𝑙, and the identity matrix forHres
𝑙.
Hres
𝑙Hpre
𝑙Hpost
𝑙Absolute Loss Gap
0.0
✓ −0.022
✓ ✓ −0.025
✓ ✓ ✓ −0.027
3.1. Numerical Instability
While the residual mapping Hres
𝑙is instrumental for performance, its sequential application
poses a significant risk to numerical stability. As detailed in Eq. (4), when HC is extended across
multiple layers, the effective signal propagation from layer𝑙to𝐿is governed by the composite
mappingÎ𝐿−𝑙
𝑖=1Hres
𝐿−𝑖. Since the learnable mapping Hres
𝑙is unconstrained, this composite mapping
inevitably deviates from the identity mapping. Consequently, the signal magnitude is prone to
explosion or vanishing during both the forward pass and backpropagation. This phenomenon
undermines the fundamental premise of residual learning, which relies on unimpeded signal
flow, thereby destabilizing the training process in deeper or larger-scale models.
Empirical evidence supports this analysis. We observe unstable loss behavior in large-scale
experiments, as illustrated in Fig. 2. TakingmHC as the baseline, HC exhibits an unexpected
loss surge around the 12k step, which is highly correlated with the instability in the gradient
norm. Furthermore, the analysis on Hres
𝑙validates the mechanism of this instability. To quantify
how the composite mappingÎ𝐿−𝑙
𝑖=1Hres
𝐿−𝑖amplifies signals along the residual stream, we utilize
two metrics. The first, based on the maximum absolute value of the row sums of the composite
mapping, captures the worst-case expansion in the forward pass. The second, based on the
maximum absolute column sum, corresponds to the backward pass. We refer to these metrics
as theAmax Gain Magnitudeof the composite mapping. As shown in Fig. 3 (b), the Amax Gain
Magnitude yields extreme values with peaks of 3000, a stark divergence from 1 that confirms
the presence of exploding residual streams.
60 10000 20000 30000 40000 50000
Steps-0.0020.0000.0020.0040.0060.0080.0100.012Absolute Loss Gap
(a) Absolute Training Loss Gap vs. Training StepsmHC
HC
0 10000 20000 30000 40000 50000
Steps0.000.050.100.150.200.25Grad Norm
(b) Gradient Norm vs. Training StepsmHC
HCFigure 2|Training Instability of Hyper-Connections (HC).This figure illustrates (a) the absolute
loss gap of HC relative tomHC, and (b) the comparisons of gradient norms. All results are based
on 27B models.
0 10 20 30 40 50 60
Layer Index l100101Amax Gain Magnitude
(a) Single-Layer MappingHres
l Forward Signal Gain
Hres
l Backward Gradient Gain
0 10 20 30 40 50 60
Layer Index l101102103104105Amax Gain Magnitude
(b) Composite Mapping/productdisplayl
i=1Hres
l+1−i Forward Signal Gain
/productdisplay61−l
i=1Hres
61−i Backward Gradient Gain
Figure 3|Propagation Instability of Hyper-Connections (HC).This figure illustrates the
propagation dynamics of (a) the single-layer mapping Hres
𝑙and (b) the composite mappingÎ𝐿−𝑙
𝑖=1Hres
𝐿−𝑖within the 27B model. The layer index 𝑙(x-axis) unrolls each standard Transformer
block into two independent layers (Attention and FFN). The Amax Gain Magnitude (y-axis) is
calculated as the maximum absolute row sum (for the forward signal) and column sum (for the
backward gradient), averaged over all tokens in a selected sequence.
3.2. System Overhead
While the computational complexity of HC remains manageable due to the linearity of the
additional mappings, the system-level overhead prevents a non-negligible challenge. Specifically,
memory access (I/O) costs often constitute one of the primary bottlenecks in modern model
architectures, which is widely referred to as the “memory wall” (Dao et al., 2022). This bottleneck
is frequently overlooked in architectural design, yet it decisively impacts runtime efficiency.
Focusing on the widely adopted pre-norm Transformer (Vaswani et al., 2017) architecture,
we analyze the I/O patterns inherent to HC. Tab. 2 summarizes the per token memory access
overhead in a single residual layer introduced by the 𝑛-stream residual design. The analysis
reveals that HC increases the memory access cost by a factor approximately proportional to 𝑛.
This excessive I/O demand significantly degrades training throughput without the mitigation of
fused kernels. Besides, since Hpre
𝑙,Hpost
𝑙, andHres
𝑙involve learnable parameters, their interme-
diate activations are required for backpropagation. This results in a substantial increase in the
GPU memory footprint, often necessitating gradient checkpointing to maintain feasible memory
usage. Furthermore, HC requires 𝑛-fold more communication cost in pipeline parallelism (Qi
et al., 2024), leading to larger bubbles and decreasing the training throughput.
7Table 2|Comparison of Memory Access Costs Per Token.This analysis accounts for the
overhead introduced by the residual stream maintenance in the forward pass, excluding the
internal I/O of the layer functionF.
Method Operation Read (Elements) Write (Elements)
Residual
ConnectionResidual Merge 2𝐶 𝐶
Total I/O 2C C
Hyper-
ConnectionsCalculateHpre
𝑙,Hpost
𝑙,Hres
𝑙𝑛𝐶 𝑛2+2𝑛
Hpre
𝑙𝑛𝐶+𝑛 𝐶
Hpost
𝑙𝐶+𝑛 𝑛𝐶
Hres
𝑙𝑛𝐶+𝑛2𝑛𝐶
Residual Merge 2𝑛𝐶 𝑛𝐶
Total I/O(5n+1)C+n2+2n(3n+1)C+n2+2n
4. Method
4.1. Manifold-Constrained Hyper-Connections
Drawing inspiration from the identity mapping principle (He et al., 2016b), the core premise
ofmHC is to constrain the residual mapping Hres
𝑙onto a specific manifold. While the original
identity mapping ensures stability by enforcing Hres
𝑙=I, it fundamentally precludes information
exchange within the residual stream, which is critical for maximizing the potential of multi-
stream architectures. Therefore, we propose projecting the residual mapping onto a manifold
that simultaneously maintains the stability of signal propagation across layers and facilitates
mutual interaction among residual streams to preserve the model’s expressivity. To this end,
we restrictHres
𝑙to be a doubly stochastic matrix, which has non-negative entries where both
the rows and columns sum to 1. Formally, let Mresdenote the manifold of doubly stochastic
matrices (also known as the Birkhoff polytope). We constrainHres
𝑙toPMres(Hres
𝑙), defined as:
PMres(Hres
𝑙)≔
Hres
𝑙∈R𝑛×𝑛|Hres
𝑙1𝑛=1𝑛,1⊤
𝑛Hres
𝑙=1⊤
𝑛,Hres
𝑙⩾0	
, (6)
where1 𝑛represents the𝑛-dimensional vector of all ones.
It is worth noting that when 𝑛=1, the doubly stochastic condition degenerates to the scalar
1, thereby recovering the original identity mapping. The choice of double stochasticity confers
several rigorous theoretical properties beneficial for large-scale model training:
1.Norm Preservation:The spectral norm of a doubly stochastic matrix is bounded by 1
(i.e.,∥Hres
𝑙∥2≤1). This implies that the learnable mapping is non-expansive, effectively
mitigating the gradient explosion problem.
2.Compositional Closure:The set of doubly stochastic matrices is closed under matrix
multiplication. This ensures that the composite residual mapping across multiple layers,Î𝐿−𝑙
𝑖=1Hres
𝐿−𝑖, remains doubly stochastic, thereby preserving stability throughout the entire
depth of the model.
3.Geometric Interpretation via the Birkhoff Polytope:The set Mresforms the Birkhoff
polytope, which is the convex hull of the set of permutation matrices. This provides a
clear geometric interpretation: the residual mapping acts as a convex combination of
permutations. Mathematically, the repeated application of such matrices tends to increase
8the mixing of information across streams monotonically, effectively functioning as a robust
feature fusion mechanism.
Additionally, we impose non-negativity constraints on the input mappings Hpre
𝑙and output
mappingsHpost
𝑙. This constrain prevents signal cancellation arising from the composition of
positive and negative coefficients, which can also be considered as a special manifold projection.
4.2. Parameterization and Manifold Projection
In this section, we detail the calculation process of Hpre
𝑙,Hpost
𝑙,andHres
𝑙inmHC. Given the
input hidden matrixx 𝑙∈R𝑛×𝐶at the𝑙-th layer, we first flatten it into a vector ®x𝑙=vec( x𝑙)∈R1×𝑛𝐶
to preserve full context information. Then, we follow the original HC formulation to get the
dynamic mappings and the static mappings as follows:
 
®x′
𝑙=RMSNorm(®x𝑙)
˜Hpre
𝑙=𝛼pre
𝑙·(®x′
𝑙𝜑pre
𝑙)+bpre
𝑙
˜Hpost
𝑙=𝛼post
𝑙·(®x′
𝑙𝜑post
𝑙)+bpost
𝑙
˜Hres
𝑙=𝛼res
𝑙·mat(®x′
𝑙𝜑res
𝑙)+bres
𝑙,(7)
where𝜑pre
𝑙,𝜑post
𝑙∈R𝑛𝐶×𝑛and𝜑res
𝑙∈R𝑛𝐶×𝑛2are linear projections for dynamic mappings and
mat(·)is a reshape function fromR1×𝑛2toR𝑛×𝑛.
Then, the final constrained mappings are obtained via:
 
Hpre
𝑙=𝜎( ˜Hpre
𝑙)
Hpost
𝑙=2𝜎( ˜Hpost
𝑙)
Hres
𝑙=Sinkhorn-Knopp( ˜Hres
𝑙),(8)
where𝜎(·) denotes the Sigmoid function. The Sinkhorn-Knopp(·) operator firstly makes all
elements to be positive via an exponent operator and then conducts iterative normalization
process that alternately rescales rows and columns to sum to 1. Specifically, given a positive
matrixM(0)=exp( ˜Hres
𝑙)as the start point, the normalization iteration proceeds as:
M(𝑡)=T𝑟
T𝑐(M(𝑡−1))
, (9)
whereT𝑟andT𝑐denote row and column normalization, respectively. This process converges to a
doubly stochastic matrix Hres
𝑙=M(𝑡max)as𝑡max→∞ . We choose 𝑡max=20 as a practical value in
our experiments.
4.3. Efficient Infrastructure Design
In this section, we detail the infrastructure design tailored formHC. Through rigorous optimiza-
tion, we implementmHC (with 𝑛=4) in large-scale models with a marginal training overhead
of only 6.7%.
4.3.1. Kernel Fusion
Observing that RMSNorm inmHC imposes significant latency when operating on the high-
dimensional hidden state ®x𝑙∈R1×𝑛𝐶, we reorder the dividing-by-norm operation to follow the
9matrix multiplication. This optimization maintains mathematical equivalence while improving
efficiency. Furthermore, we employ mixed-precision strategies to maximize numerical accuracy
without compromising speed, and fuse multiple operations with shared memory access into
unified compute kernels to reduce memory bandwidth bottlenecks. Based on the inputs and
parameters detailed in Eq. (10) to(13), we implement three specializedmHC kernels to compute
Hpre
𝑙,Hpost
𝑙, andHres
𝑙. In these kernels, the biases and linear projections are consolidated intob 𝑙
and𝜑𝑙, and the RMSNorm weight is also absorbed in𝜑 𝑙.
•Eq.(14) to(15): We develop a unified kernel that fuses two scans on ®x𝑙, leveraging ma-
trix multiplication units to maximize memory bandwidth utilization. The backward
pass—comprising two matrix multiplications—is similarly consolidated into a single ker-
nel, eliminating redundant reloading of ®x𝑙. Both kernels feature a finely tuned pipeline
(load, cast, compute, store) to efficiently handle mixed-precision processing.
•Eq.(16) to(18): These lightweight operations on small coefficients are opportunistically
fused into a single kernel, significantly reducing kernel launch overhead.
•Eq.(19): We implement the Sinkhorn-Knopp iteration within a single kernel. For the
backward pass, we derive a custom backward kernel that recomputes the intermediate
results on-chip and traverses the entire iteration.
𝜑𝑙: tfloat32[𝑛𝐶,𝑛2+2𝑛](10)
®x𝑙: bfloat16[1,𝑛𝐶](11)
𝛼pre
𝑙,𝛼post
𝑙,𝛼res
𝑙: float32 Scalars (12)
b𝑙: float32[1,𝑛2+2𝑛](13)h˜˜Hpre
𝑙,˜˜Hpost
𝑙,˜˜Hres
𝑙i
: float32= ®x𝑙𝜑𝑙 (14)
𝑟: float32=®x𝑙
2/√
𝑛𝐶(15)
h
˜Hpre
𝑙,˜Hpost
𝑙,˜Hres
𝑙i
: float32=1/𝑟h
𝛼pre
𝑙˜˜Hpre
𝑙,𝛼post
𝑙˜˜Hpost
𝑙,𝛼res
𝑙˜˜Hres
𝑙i
+b𝑙 (16)
Hpre
𝑙: float32=𝜎
˜Hpre
𝑙
(17)
Hpost
𝑙: float32=2𝜎
˜Hpost
𝑙
(18)
Hres
𝑙: float32=Sinkhorn-Knopp