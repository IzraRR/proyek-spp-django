# pembayaran/views.py

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Siswa, Tagihan, Pembayaran
from django.conf import settings 
from django.db.models import Sum, Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
import json
import midtransclient
import uuid

@login_required 
def dashboard_siswa(request):
    try:
        siswa = request.user.siswa
    except Siswa.DoesNotExist:
        return render(request, 'pembayaran/bukan_siswa.html')

    # 1. Ambil tagihan yang BELUM LUNAS
    tagihan_belum_lunas = Tagihan.objects.filter(
        siswa=siswa
    ).exclude(status='LUNAS').order_by('tanggal_dibuat')

    # 2. Ambil tagihan yang SUDAH LUNAS
    tagihan_lunas = Tagihan.objects.filter(
        siswa=siswa, 
        status='LUNAS'
    ).prefetch_related('pembayaran_set').order_by('-tanggal_dibuat')

    # 3. Hitung total dan jumlah tunggakan
    # Gunakan filter yang sama dengan tagihan_belum_lunas untuk konsistensi
    ringkasan_tunggakan = tagihan_belum_lunas.aggregate(
        total=Sum('jumlah'),
        jumlah=Sum(1) # Hitung jumlah tagihan
    )
    
    total_tunggakan = ringkasan_tunggakan.get('total') or 0
    jumlah_tunggakan = ringkasan_tunggakan.get('jumlah') or 0

    context = {
        'siswa': siswa,
        'tagihan_belum_lunas': tagihan_belum_lunas,
        'tagihan_lunas': tagihan_lunas,
        'total_tunggakan': total_tunggakan,
        'jumlah_tunggakan': jumlah_tunggakan,
        'midtrans_client_key': settings.MIDTRANS_CLIENT_KEY, # Kirim client key ke template
    }
    return render(request, 'pembayaran/dashboard.html', context)


# ----------------------------------------------------------------
# --- FUNGSI 'buat_transaksi'
# ----------------------------------------------------------------
@login_required
def buat_transaksi(request, tagihan_id):
    # Konfigurasi Midtrans
    snap = midtransclient.Snap(
        is_production=True, # Set False untuk Sandbox
        server_key=settings.MIDTRANS_SERVER_KEY,
        client_key=settings.MIDTRANS_CLIENT_KEY
    )

    try:
        # 1. Ambil data tagihan dari database
        tagihan = Tagihan.objects.get(id=tagihan_id, siswa=request.user.siswa)
        jumlah_bayar = int(tagihan.sisa_tagihan)
        
        # 2. Cek apakah tagihan sudah lunas
        if tagihan.status == 'LUNAS':
            return JsonResponse({'error': 'Tagihan ini sudah lunas.'}, status=400)

        # 3. Buat order_id yang unik
        order_id = f"SPP-{tagihan.id}-{uuid.uuid4()}" 

        # 4. Siapkan parameter transaksi
        transaction_params = {
            'transaction_details': {
                'order_id': order_id,
                'gross_amount': int(tagihan.jumlah), # Jumlah harus integer
            },
            'item_details': [{
                'id': tagihan.id,
                'price': int(tagihan.jumlah),
                'quantity': 1,
                'name': tagihan.judul,
            }],
            'customer_details': {
                'first_name': tagihan.siswa.nama_lengkap,
                'email': request.user.email, # Asumsi User punya email
            }
        }

        # 5. Panggil API Midtrans untuk dapatkan token
        transaction_token = snap.create_transaction(transaction_params)
        
        # 6. Kirim token kembali ke frontend
        return JsonResponse({'token': transaction_token['token']})

    except Tagihan.DoesNotExist:
        return JsonResponse({'error': 'Tagihan tidak ditemukan.'}, status=404)
    except Exception as e:
        print(f"Error Midtrans: {e}")
        return JsonResponse({'error': f'Terjadi kesalahan: {str(e)}'}, status=500)

# ----------------------------------------------------------------
# --- FUNGSI WEBHOOK (Struktur try-except sudah diperbaiki)
# ----------------------------------------------------------------

# 1. Konfigurasi "Core API" client Midtrans untuk verifikasi
core_api = midtransclient.CoreApi(
    is_production=True,
    server_key=settings.MIDTRANS_SERVER_KEY,
    client_key=settings.MIDTRANS_CLIENT_KEY
)

@login_required
def lihat_kwitansi(request, pembayaran_id):
    # 1. Ambil data pembayaran, atau tampilkan 404 jika tidak ditemukan
    pembayaran = get_object_or_404(Pembayaran, id=pembayaran_id)

    # 2. Keamanan: Pastikan siswa yang login adalah pemilik kwitansi ini
    if pembayaran.tagihan.siswa != request.user.siswa:
        # Jika bukan, kembalikan ke dashboard (atau tampilkan error)
        messages.error(request, "Anda tidak memiliki izin untuk melihat kwitansi ini.")
        return redirect('dashboard')

    context = {
        'pembayaran': pembayaran,
    }

    return render(request, 'pembayaran/kwitansi.html', context)


@csrf_exempt
def webhook_midtrans(request):
    if request.method == 'POST':
        try:
            # 1. Ambil data dari Midtrans
            body = json.loads(request.body)
            transaction_status = body.get('transaction_status')
            order_id = body.get('order_id')
            transaction_id = body.get('transaction_id') # <-- INI ID OTOMATIS DARI MIDTRANS
            payment_type = body.get('payment_type')
            gross_amount = Decimal(body.get('gross_amount')) # Jumlah yang dibayar kali ini

            print(f"WEBHOOK: Order {order_id}, Status {transaction_status}, ID Transaksi {transaction_id}")

            # 2. Cari Tagihan Terkait
            try:
                # Format order_id kita: "SPP-ID_TAGIHAN-UUID"
                tagihan_id = order_id.split('-')[1]
                tagihan = Tagihan.objects.get(id=tagihan_id)
            except (Tagihan.DoesNotExist, IndexError, ValueError) as e:
                print(f"Error cari tagihan: {e}")
                return HttpResponse(status=404)

            # 3. LOGIKA UTAMA
            if transaction_status == 'settlement':
                # "Capture" atau "Settlement" berarti uang masuk/berhasil
                
                # A. Cek apakah transaksi ID ini sudah pernah dicatat sebelumnya?
                # Gunakan get_or_create agar tidak ada duplikasi data jika Midtrans kirim notif 2x
                pembayaran, created = Pembayaran.objects.get_or_create(
                    id_transaksi_gateway=transaction_id, # Kunci uniknya adalah ID dari Midtrans
                    defaults={
                        'tagihan': tagihan,
                        'jumlah_bayar': gross_amount,
                        'metode_pembayaran': payment_type,
                        # tanggal_bayar akan otomatis terisi 'now' karena auto_now_add di models
                    }
                )

                # B. JIKA ini adalah data pembayaran BARU (created=True), update saldo Tagihan
                if created:
                    # Tambahkan jumlah yang baru dibayar ke total yang sudah dibayar
                    tagihan.jumlah_terbayar += gross_amount
                    
                    # Panggil save() agar logika status (LUNAS/BELUM) di models.py berjalan
                    tagihan.save() 
                    
                    print(f"Pembayaran baru Rp {gross_amount} diterima. Total terbayar: {tagihan.jumlah_terbayar}")
                else:
                    print("Notifikasi duplikat diterima, diabaikan.")

            elif transaction_status in ['expire', 'cancel', 'deny']:
                # Jika pembayaran gagal, kita tidak perlu mengubah saldo 'jumlah_terbayar'
                # Kita hanya perlu memastikan status tagihan tidak nyangkut di 'PENDING'
                if tagihan.status == 'PENDING':
                    # Kembalikan status sesuai kondisi uang
                    tagihan.save() # save() akan otomatis hitung ulang: kalau 0 jadi BELUM_LUNAS
                    print(f"Transaksi {order_id} gagal. Status dikembalikan.")

            return HttpResponse(status=200)

        except json.JSONDecodeError:
            return HttpResponse(status=400)
        except Exception as e:
            print(f"Error Webhook: {e}")
            return HttpResponse(status=500)
    
    return HttpResponse(status=405)