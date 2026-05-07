import pandas as pd
import numpy as np
from products.models import Product, UserBehavior
from django.db.models import Case, When
from django.utils import timezone


def item_based_recommendation(user_id, preference='', top_n=6):
    """
    核心算法：基于时间感知与会话窗口的协同过滤 (Time & Session Aware Item-CF)
    1. 全局衰减：越早的购买行为权重越低。
    2. 关联衰减：同用户购买两件商品的时间差越大，关联性越低（区分连续购买 vs 独立购买）。
    """
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return []

    behaviors = UserBehavior.objects.all().values('user_id', 'product_id', 'action_type', 'timestamp')
    if not behaviors:
        return []

    df = pd.DataFrame(list(behaviors))

    # 1. 定义基础权重
    weights = {1: 1, 2: 3, 3: 4, 4: 5}
    df['base_score'] = df['action_type'].map(weights)

    # ==========================================
    # +++ 步骤一：数据清洗与全局衰减 (你之前已经理解的部分) +++
    # ==========================================
    # 聚合每个用户对每件商品的最高分和最新操作时间，防止重复操作导致数据膨胀
    user_item_df = df.groupby(['user_id', 'product_id']).agg({
        'base_score': 'max',
        'timestamp': 'max'
    }).reset_index()

    now = timezone.now()
    user_item_df['days_from_now'] = (now - user_item_df['timestamp']).dt.total_seconds() / (24 * 3600)
    user_item_df['days_from_now'] = user_item_df['days_from_now'].clip(lower=0)

    alpha = 0.05  # 全局遗忘系数
    user_item_df['global_score'] = user_item_df['base_score'] * np.exp(-alpha * user_item_df['days_from_now'])

    if user_item_df['product_id'].nunique() < 2:
        return []

    # ==========================================
    # +++ 步骤二：核心突破！手写带时间惩罚的共现矩阵 +++
    # ==========================================
    # 1. 把表格跟自己做内连接，找出同一个用户操作过的所有【商品对】
    pairs = pd.merge(user_item_df, user_item_df, on='user_id', suffixes=('_i', '_j'))

    # 2. 踢掉自己跟自己组合的行（比如 衬衫-衬衫）
    pairs = pairs[pairs['product_id_i'] != pairs['product_id_j']]

    if pairs.empty:
        return []

    # 3. 计算同一个用户买 A 商品 和 买 B 商品的时间差（天）
    pairs['time_gap_days'] = abs((pairs['timestamp_i'] - pairs['timestamp_j']).dt.total_seconds()) / (24 * 3600)

    # 4. 定义相对时间惩罚系数 Beta
    # Beta = 0.5 意味着：如果相差0天(连续加购)，得满分；如果相差2天，权重直接砍掉63%！
    beta = 0.5

    # 5. 最终组合权重 = A的全局分 * B的全局分 * 时间差惩罚系数
    pairs['pair_weight'] = (pairs['global_score_i'] * pairs['global_score_j']) * np.exp(-beta * pairs['time_gap_days'])

    # 6. 把所有用户贡献的组合权重加起来，这就是两件商品真实的相似度矩阵！
    item_sim_df = pairs.groupby(['product_id_i', 'product_id_j'])['pair_weight'].sum().unstack(fill_value=0)

    # 7. 余弦归一化处理（防止爆款商品霸榜，类似 sklearn 内部做的事）
    item_norms = user_item_df.groupby('product_id')['global_score'].apply(lambda x: np.sqrt((x ** 2).sum()))
    item_sim_df = item_sim_df.div(item_norms, axis=0).div(item_norms, axis=1).fillna(0)

    # ==========================================
    # +++ 步骤三：为当前用户计算推荐分 (保持原样即可) +++
    # ==========================================
    user_history = user_item_df[user_item_df['user_id'] == user_id]['product_id'].unique()
    if len(user_history) == 0:
        return []

    recommend_scores = {}
    for product_id in user_history:
        if product_id not in item_sim_df.index: continue

        similar_products = item_sim_df[product_id].sort_values(ascending=False)
        for sim_product, similarity in similar_products.items():
            if sim_product in user_history: continue

            recommend_scores.setdefault(sim_product, 0)
            recommend_scores[sim_product] += similarity

    # VIP 偏好干预
    if preference and recommend_scores:
        candidate_ids = list(recommend_scores.keys())
        candidates = Product.objects.filter(id__in=candidate_ids).values('id', 'tags')
        tag_dict = {item['id']: item['tags'] for item in candidates}

        for pid in recommend_scores:
            tags = tag_dict.get(pid, '')
            if tags and preference in tags:
                recommend_scores[pid] *= 1.5

                # 排序并取前 N 个
    sorted_products = sorted(recommend_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    if not sorted_products:
        return []

    recommended_ids = [p[0] for p in sorted_products]
    preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(recommended_ids)])
    return Product.objects.filter(id__in=recommended_ids).order_by(preserved_order)