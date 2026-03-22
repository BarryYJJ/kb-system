# Attention Residuals (Moonshot AI / Kimi)

**来源**: Moonshot AI, GitHub: MoonshotAI/Attention-Residuals, 2026-03-15

**类型**: text

**入库时间**: 2026-03-17T08:26:50.835339

---

ATTENTIONRESIDUALS
TECHNICALREPORT OFATTENTIONRESIDUALS
Kimi Team
/gtbhttps://github.com/MoonshotAI/Attention-Residuals
ABSTRACT
Residual connections [12] with PreNorm [60] are standard in modern LLMs, yet they accumulate
all layer outputs with fixed unit weights. This uniform aggregation causes uncontrolled hidden-state
growth with depth, progressively diluting each layer’s contribution [27]. We proposeAttention
Residuals (AttnRes), which replaces this fixed accumulation with softmax attention over preceding
layer outputs, allowing each layer to selectively aggregate earlier representations with learned, input-
dependent weights. To address the memory and communication overhead of attending over all
preceding layer outputs for large-scale model training, we introduceBlock AttnRes, which partitions
layers into blocks and attends over block-level representations, reducing the memory footprint while
preserving most of the gains of full AttnRes. Combined with cache-based pipeline communication
and a two-phase computation strategy, Block AttnRes becomes a practical drop-in replacement for
standard residual connections with minimal overhead.
Scaling law experiments confirm that the improvement is consistent across model sizes, and ablations
validate the benefit of content-dependent depth-wise selection. We further integrate AttnRes into
the Kimi Linear architecture [69] (48B total / 3B activated parameters) and pre-train on 1.4T tokens,
where AttnRes mitigates PreNorm dilution, yielding more uniform output magnitudes and gradient
distribution across depth, and improves downstream performance across all evaluated tasks.
Embedding...AttentionMoEAttentionMoEOutput
(a) Standard ResidualsEmbedding...αAttentionαMoEαAttentionαMoE
wwwwOutput
αw
ααααα
(b) Full Attention ResidualsEmbedding···Blockn-2Blockn-1AttentionMoEAttentionMoEOutput
α
αααα
ααααα
wwwww
AttnRes Op(α)wQKV
(c) Block Attention Residuals
Figure 1: Overview of Attention Residuals.(a)Standard Residuals: standard residual connections with uniform additive accumulation.
(b)Full AttnRes: each layer selectively aggregates all previous layer outputs via learned attention weights.(c)Block AttnRes: layers
are grouped into blocks, reducing memory fromO(Ld)toO(Nd).Attention ResidualsTECHNICALREPORT
1 Introduction
Standard residual connections [12] are thede factobuilding block of modern LLMs [35, 51, 9]. The update hl=
hl−1+fl−1(hl−1)is widely understood as agradient highwaythat lets gradients bypass transformations via identity
mappings, enabling stable training at depth. Yet residuals also play a second role that has received less attention.
Unrolling the recurrence shows that every layer receives the same uniformly-weighted sum of all prior layer outputs;
residuals define how information aggregates across depth. Unlike sequence mixing and expert routing, which now
employ learnable input-dependent weighting [53, 20, 9], this depth-wise aggregation remains governed by fixed unit
weights, with no mechanism to selectively emphasize or suppress individual layer contributions.
In practice, PreNorm [60] has become the dominant paradigm, yet its unweighted accumulation causes hidden-state
magnitudes to grow as O(L) with depth, progressively diluting each layer’s relative contribution [27]. Early-layer
information is buried and cannot be selectively retrieved; empirically, a significant fraction of layers can be pruned with
minimal loss [11]. Recent efforts such as scaled residual paths [54] and multi-stream recurrences [72] remain bound to
the additive recurrence, while methods that do introduce cross-layer access [36, 56] are difficult to scale. The situation
parallels the challenges that recurrent neural networks (RNNs) faced over the sequence dimension before attention
mechanism provided an alternative.
We observe a formal duality between depth-wise accumulation and the sequential recurrence in RNNs. Building
on this duality, we proposeAttention Residuals (AttnRes), which replaces the fixed accumulation hl=P
ivi
withhl=P
iαi→l·vi, where αi→laresoftmax attention weights computed from a single learned pseudo-query
wl∈Rdper layer. This lightweight mechanism enables selective, content-aware retrieval across depth with only one
d-dimensional vector per layer. Indeed, standard residual connections and prior recurrence-based variants can all be
shown to perform depth-wiselinearattention; AttnRes generalizes them to depth-wise softmax attention, completing
for depth the same linear-to-softmaxtransition that proved transformative over sequences (§6.2, §6.1).
In standard training, Full AttnRes adds negligible overhead, since the layer outputs it requires are already retained for
backpropagation. At scale, however, activation recomputation and pipeline parallelism are routinely employed, and these
activations must now be explicitly preserved and communicated across pipeline stages. We introduceBlock AttnResto
maintain efficiency in this regime: layers are partitioned into Nblocks, each reduced to a single representation via
standard residuals, with cross-block attention applied only over the Nblock-level summaries. This brings both memory
and communication down to O(Nd) , and together with infrastructure optimizations (§4), Block AttnRes serves as a
drop-in replacement for standard residual connections with marginal training cost and negligible inference latency
overhead.
Scaling law experiments confirm that AttnRes consistently outperforms the baseline across compute budgets, with
Block AttnRes matching the loss of a baseline trained with 1.25× more compute. We further integrate AttnRes into
the Kimi Linear architecture [69] (48B total / 3B activated parameters) and pre-train on 1.4T tokens. Analysis of
the resulting training dynamics reveals that AttnRes mitigates PreNorm dilution, with output magnitudes remaining
bounded across depth and gradient norms distributing more uniformly across layers. On downstream benchmarks, our
final model improves over the baseline across all evaluated tasks.
Contributions
•Attention Residuals.We propose AttnRes, which replaces fixed residual accumulation with learned softmax
attention over depth, and its scalable variant Block AttnRes that reduces memory and communication from O(Ld) to
O(Nd) . Through a unified structured-matrix analysis, we show that standard residuals and prior recurrence-based
variants correspond to depth-wiselinearattention, while AttnRes performs depth-wisesoftmaxattention.
•Infrastructure for scale.We develop system optimizations that make Block AttnRes practical and efficient at scale,
including cross-stage caching that eliminates redundant transfers under pipeline parallelism and a two-phase inference
strategy that amortizes cross-block attention via online softmax [31]. The resulting training overhead is marginal,
and the inference latency overhead is less than 2% on typical inference workloads.
•Comprehensive evaluation and analysis.We validate AttnRes through scaling law experiments, component
ablations, and downstream benchmarks on a 48B-parameter model pre-trained on 1.4T tokens, demonstrating
consistent improvements over standard residual connections. Training dynamics analysis further reveals that AttnRes
mitigates PreNorm dilution, yielding bounded hidden-state magnitudes and more uniform gradient distribution across
depth.
2Attention ResidualsTECHNICALREPORT
2 Motivation
Notation.Consider a batch of input sequences with shape B×T×d , where Bis the batch size, Tis the sequence
length, and dis the hidden dimension. For clarity, we write formulas for a single token: hl∈Rddenotes the hidden state
entering layer l, where l∈ {1, . . . , L} is the layer index and Lis the total number of layers. The token embedding is h1.
The function flrepresents the transformation applied by layer l. In Transformer models, we treat each self-attention or
MLP as an individuallayer.
2.1 Training Deep Networks via Residuals
Residual Learning.Residual learning [12] proves to be a critical technique in training deep networks as it allows
gradients to bypass transformations. Specifically, each layer updates the hidden state as:
hl=hl−1+fl−1(hl−1)
Expanding this recurrence, the hidden state at layer lis the sum of the embedding and all preceding layer outputs:
hl=h 1+Pl−1
i=1fi(hi). The key insight behind residual connections isidentity mapping: each layer preserves a direct
path for both information and gradients to flow unchanged. During back-propagation, the gradient with respect to an
intermediate hidden state is:
∂L
∂hl=∂L
∂hL·L−1Y
j=l
I+∂fj
∂hj
Expanding this product yields Iplus higher-order terms involving the layer Jacobians ∂fj/∂hj. The identity term is
always preserved, providing a direct gradient path from the loss to any layer regardless of depth.
Generalizing Residuals.While effective, the fixed unit coefficients in the residual update treat every layer’s con-
tribution uniformly, offering no mechanism to adapt the mixing across depth. Highway networks [45] relax this by
introducing learned element-wise gates:
hl= (1−g l)⊙h l−1+gl⊙fl−1(hl−1)
where gl∈[0,1]dinterpolates between the transformation and the identity path. More generally, both are instances
of a weighted recurrence hl=α l·hl−1+βl·fl−1(hl−1), with residual setting αl=βl=1and Highway setting
αl=1−g l, βl=gl.
Limitations.Whether fixed or gated, both approaches share a fundamental constraint: each layer can only access
its immediate input hl−1, a single compressed state that conflates all earlier layer outputs, rather than the individual
outputs themselves. This entails several limitations: (1)no selective access: different layer types (e.g., attention vs.
MLP) receive the same aggregated state, despite potentially benefiting from different weightings; (2)irreversible loss:
information lost through aggregation cannot be selectively recovered in deeper layers; and (3)output growth: later
layers learn increasingly larger outputs to gain influence over the accumulated residual, which can destabilize training.
These limitations motivate a mechanism that lets each layer selectively aggregate information from all preceding layers.
3 Attention Residuals: A Unified View of Time and Depth
The limitations discussed above are reminiscent of similar bottlenecks in sequence modeling, suggesting that we seek
similar solutions for the depth dimension.
The Duality of Time and Depth.Like RNNs over time, residual connections compress all prior information into a
single state hlover depth. For sequence modeling, the Transformer improved upon RNNs by replacing recurrence with
attention [3, 52], allowing each position to selectively access all previous positions with data-dependent weights. We
propose the same methodology for depth:
hl=α 0→l·h1+l−1X
i=1αi→l·fi(hi)(1)
where αi→lare layer-specific attention weights satisfyingPl−1
i=0αi→l= 1. Unlike sequence length (which can reach
millions of tokens), network depth is typically modest ( L <1000 ), making O(L2)attention over depth computationally
feasible. We call this approachAttention Residuals, abbreviated asAttnRes.
3Attention ResidualsTECHNICALREPORT
3.1 Full Attention Residuals
The attention weights can be written as αi→l=ϕ(q l,ki)for a kernel function ϕ:Rd×Rd→R≥0, where qland
kiare query and key vectors [23, 70]. Different choices of ϕrecover different residual variants (§6.2); we adopt
ϕ(q,k) = exp