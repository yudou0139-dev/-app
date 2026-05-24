import pandas as pd
import numpy as np
from products.models import Product, UserBehavior
from django.utils import timezone
from django.db import models
from django.db.models import Q, Case, When


def item_based_recommendation(user_id, preference='', top_n=6):
    """
    核心算法：基于时间感知与会话窗口的协同过滤 (Time & Session Aware Item-CF)
    """
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return Product.objects.none()

    # 核心修复 1：偏好映射词典（解决前端英文枚举与数据库中文标签不匹配的断层）
    pref_map = {
        'business': '商务',
        'casual': '休闲',
        'sports': '运动',
        'minimalist': '简约',
        'street': '街头',
        'outdoor': '户外',
        'vintage': '复古'
    }
    # 智能转换：如果是英文字段，翻译成中文；否则保持原样
    mapped_pref = pref_map.get(preference, preference) if preference else ''

    behaviors = UserBehavior.objects.all().values('user_id', 'product_id', 'action_type', 'timestamp')

    recommend_scores = {}
    purchased_history = []

    # 只有当全站有行为记录时，才进行 Pandas 协同过滤核心运算
    if behaviors:
        df = pd.DataFrame(list(behaviors))
        weights = {1: 1, 2: 3, 3: 4, 4: 5}
        df['base_score'] = df['action_type'].map(weights)

        # 核心修复 2：精准分离！只提取当前用户真正【购买过(4)】的商品，这部分才需要过滤不再推荐
        purchased_history = df[(df['user_id'] == user_id) & (df['action_type'] == 4)]['product_id'].unique().tolist()

        # 数据清洗与全局衰减
        user_item_df = df.groupby(['user_id', 'product_id']).agg({
            'base_score': 'max',
            'timestamp': 'max'
        }).reset_index()

        now = timezone.now()
        user_item_df['days_from_now'] = (now - user_item_df['timestamp']).dt.total_seconds() / (24 * 3600)
        user_item_df['days_from_now'] = user_item_df['days_from_now'].clip(lower=0)

        alpha = 0.05
        user_item_df['global_score'] = user_item_df['base_score'] * np.exp(-alpha * user_item_df['days_from_now'])

        if user_item_df['product_id'].nunique() >= 2:
            pairs = pd.merge(user_item_df, user_item_df, on='user_id', suffixes=('_i', '_j'))
            pairs = pairs[pairs['product_id_i'] != pairs['product_id_j']]

            if not pairs.empty:
                pairs['time_gap_days'] = abs((pairs['timestamp_i'] - pairs['timestamp_j']).dt.total_seconds()) / (
                            24 * 3600)
                beta = 0.5
                pairs['pair_weight'] = (pairs['global_score_i'] * pairs['global_score_j']) * np.exp(
                    -beta * pairs['time_gap_days'])

                item_sim_df = pairs.groupby(['product_id_i', 'product_id_j'])['pair_weight'].sum().unstack(fill_value=0)
                item_norms = user_item_df.groupby('product_id')['global_score'].apply(lambda x: np.sqrt((x ** 2).sum()))
                item_sim_df = item_sim_df.div(item_norms, axis=0).div(item_norms, axis=1).fillna(0)

                # 为当前用户计算推荐分
                user_all_history = user_item_df[user_item_df['user_id'] == user_id]['product_id'].unique().tolist()
                if len(user_all_history) > 0:
                    for pid in user_all_history:
                        if pid not in item_sim_df.index: continue
                        similar_products = item_sim_df[pid].sort_values(ascending=False)
                        for sim_product, similarity in similar_products.items():
                            # 核心修复 3：只过滤买过的商品，浏览过和收藏过的允许继续推流！
                            if sim_product in purchased_history: continue

                            recommend_scores.setdefault(sim_product, 0)
                            recommend_scores[sim_product] += similarity

    # VIP 偏好干预提权
    if mapped_pref and recommend_scores:
        candidate_ids = list(recommend_scores.keys())
        candidates = Product.objects.filter(id__in=candidate_ids).values('id', 'tags')
        tag_dict = {item['id']: item['tags'] for item in candidates}
        for pid in recommend_scores:
            tags = tag_dict.get(pid, '')
            if tags and mapped_pref in tags:
                recommend_scores[pid] *= 1.5

    # ================= 核心兜底填充逻辑 (重构版) =================
    sorted_products = sorted(recommend_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    recommended_ids = [p[0] for p in sorted_products]

    shortage = top_n - len(recommended_ids)
    fallback_ids = []

    if shortage > 0:
        # 兜底时同样只剔除已经买过的商品和推荐池里现有的商品
        exclude_ids = recommended_ids + purchased_history

        # 核心修复 4：即便没有行为数据的全新用户，也能在这里利用 mapped_pref 精准命中冷启动兜底
        if mapped_pref:
            fallback_qs = list(Product.objects.filter(
                Q(tags__icontains=mapped_pref) |
                Q(name__icontains=mapped_pref) |
                Q(description__icontains=mapped_pref)
            ).exclude(id__in=exclude_ids).order_by('-created_at')[:shortage])

            # 如果带有偏好的商品不够数，再拿普通最新商品填坑
            if len(fallback_qs) < shortage:
                rem_shortage = shortage - len(fallback_qs)
                rem_exclude = exclude_ids + [item.id for item in fallback_qs]
                rem_qs = list(Product.objects.exclude(id__in=rem_exclude).order_by('-created_at')[:rem_shortage])
                fallback_qs.extend(rem_qs)

            fallback_ids = [item.id for item in fallback_qs]
        else:
            fallback_qs = Product.objects.exclude(id__in=exclude_ids).order_by('-created_at')[:shortage]
            fallback_ids = [item.id for item in fallback_qs]

    final_ids = recommended_ids + fallback_ids

    if not final_ids:
        return Product.objects.none()

    preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(final_ids)])
    return Product.objects.filter(id__in=final_ids).order_by(preserved_order)


def get_related_products(product_id, top_n=4):
    """
    详情页的关联推荐：基于用户行为日志，找出“买过这件商品的人还买过/看过什么”
    """
    try:
        product_id = int(product_id)
    except (ValueError, TypeError):
        return Product.objects.none()

    # 1. 找出所有操作过这件商品的用户
    users_interacted = UserBehavior.objects.filter(product_id=product_id).values_list('user_id', flat=True).distinct()

    if not users_interacted:
        # 【冷启动兜底】如果这件商品还没人碰过，就推荐同分类或同标签的商品
        target_product = Product.objects.filter(id=product_id).first()
        if target_product:
            return Product.objects.filter(
                Q(category=target_product.category) | Q(tags__icontains=target_product.tags)
            ).exclude(id=product_id).order_by('?')[:top_n]  # order_by('?') 表示随机打乱
        return Product.objects.none()

    # 2. 找出这些用户还操作过哪些其他商品，并按操作频次排序 (这就是经典的 Item-to-Item 协同过滤)
    related_product_ids = UserBehavior.objects.filter(
        user_id__in=users_interacted
    ).exclude(
        product_id=product_id  # 排除当前正在看的商品本身
    ).values('product_id').annotate(
        interaction_count=models.Count('id')
    ).order_by('-interaction_count')[:top_n]

    # 3. 提取真实的商品数据返回
    recommended_ids = [item['product_id'] for item in related_product_ids]

    # 如果相关推荐不足 top_n，这里也可以加同款兜底（可选）
    if len(recommended_ids) < top_n:
        shortage = top_n - len(recommended_ids)
        target_product = Product.objects.filter(id=product_id).first()
        if target_product:
            fallback_qs = Product.objects.filter(
                Q(category=target_product.category) | Q(tags__icontains=target_product.tags)
            ).exclude(id__in=recommended_ids + [product_id]).order_by('?')[:shortage]
            recommended_ids.extend([item.id for item in fallback_qs])

    if not recommended_ids:
        return Product.objects.none()

    # 使用 preserved_order 保持排序
    preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(recommended_ids)])
    return Product.objects.filter(id__in=recommended_ids).order_by(preserved_order)