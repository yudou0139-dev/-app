import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from products.models import Product, UserBehavior


def item_based_recommendation(user_id, top_n=6):
    """
    核心算法：基于物品的协同过滤 (Item-CF)
    原理：如果你喜欢“耐克鞋”，而喜欢“耐克鞋”的人也喜欢“阿迪袜”，系统就会推荐“阿迪袜”给你。
    """
    # 1. 从数据库读取用户行为 (View=1, Cart=3, Buy=5)
    behaviors = UserBehavior.objects.all().values('user_id', 'product_id', 'action_type')
    if not behaviors:
        return []  # 没有数据，无法计算

    # 2. 转化为 Pandas 表格
    df = pd.DataFrame(list(behaviors))

    # 3. 定义权重 (购买权重最高)
    weights = {1: 1, 2: 3, 3: 4, 4: 5}
    df['score'] = df['action_type'].map(weights)

    # 4. 生成透视表 (行=用户, 列=商品, 值=分数)
    user_item_matrix = df.pivot_table(index='user_id', columns='product_id', values='score', aggfunc='max').fillna(0)

    # 5. 如果商品太少，无法计算相似度，直接返回
    if user_item_matrix.shape[1] < 2:
        return []

    # 6. 计算商品之间的相似度 (余弦相似度)
    item_similarity = cosine_similarity(user_item_matrix.T)
    item_sim_df = pd.DataFrame(item_similarity, index=user_item_matrix.columns, columns=user_item_matrix.columns)

    # 7. 获取当前用户交互过的商品
    try:
        user_history = df[df['user_id'] == user_id]['product_id'].unique()
    except:
        return []  # 新用户

    # 8. 逐个累加推荐分
    recommend_scores = {}
    for product_id in user_history:
        if product_id not in item_sim_df.index: continue

        # 找出与该商品相似的其他商品
        similar_products = item_sim_df[product_id].sort_values(ascending=False)

        for sim_product, similarity in similar_products.items():
            if sim_product in user_history: continue  # 过滤掉买过的

            recommend_scores.setdefault(sim_product, 0)
            recommend_scores[sim_product] += similarity

    # 9. 排序并取前 N 个
    sorted_products = sorted(recommend_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    recommended_ids = [p[0] for p in sorted_products]

    # 10. 既然算出来了 ID，去数据库把商品详情拿出来
    return Product.objects.filter(id__in=recommended_ids)