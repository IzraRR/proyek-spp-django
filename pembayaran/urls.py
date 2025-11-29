from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Halaman utama (dashboard siswa)
    path('', views.dashboard_siswa, name='dashboard'),

    # Halaman Login / Logout bawaan Django
    path('login/', auth_views.LoginView.as_view(template_name='pembayaran/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # URL ini akan dipanggil oleh JavaScript fetch()
    path('bayar/<int:tagihan_id>/', views.buat_transaksi, name='buat_transaksi'),
    path('webhook/midtrans/', views.webhook_midtrans, name='webhook_midtrans'),

    # Kwitansi pembayaran
    path('kwitansi/<int:pembayaran_id>/', views.lihat_kwitansi, name='lihat_kwitansi'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)