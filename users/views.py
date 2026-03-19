from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from .models import UserProfile

class RegisterView(APIView):
    """用户注册接口"""

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'error': '用户名和密码不能为空'}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({'error': '该用户名已存在'}, status=400)

        user = User.objects.create_user(username=username, password=password)
        return Response({'message': '注册成功', 'user_id': user.id}, status=201)


class LoginView(APIView):
    """用户登录接口"""

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)  # 记录登录状态
            return Response({
                'message': '登录成功',
                'user_id': user.id,
                'username': user.username
            })
        return Response({'error': '账号或密码错误'}, status=400)



class UpdateProfileView(APIView):
    """完善信息并解锁 VIP 接口"""
    def post(self, request):
        # 实际开发中通常用 Token 获取用户，为了方便您目前 Postman 调试，先直接传 user_id
        user_id = request.data.get('user_id')
        height = request.data.get('height')
        weight = request.data.get('weight')
        style_preference = request.data.get('style_preference')

        if not user_id:
            return Response({'error': '缺少用户ID'}, status=400)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': '用户不存在'}, status=404)

        # 获取用户的资料表（如果没有则自动创建一张）
        profile, created = UserProfile.objects.get_or_create(user=user)

        # 保存前端传过来的数据
        if height: profile.height = int(height)
        if weight: profile.weight = int(weight)
        if style_preference: profile.style_preference = style_preference

        # 核心逻辑：只要调用了这个接口完善数据，立刻升级为 VIP
        profile.is_vip = True
        profile.save()

        return Response({
            'message': '信息完善成功，已为您解锁 VIP 专属衣橱！',
            'is_vip': True
        }, status=200)