# pembayaran/views.py

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Siswa, Tagihan, Pembayaran
from django.conf import settings 
from django.db.models import Sum, Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
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
        is_production=False, # Set False untuk Sandbox
        server_key=settings.MIDTRANS_SERVER_KEY,
        client_key=settings.MIDTRANS_CLIENT_KEY
    )

    try:
        # 1. Ambil data tagihan dari database
        tagihan = Tagihan.objects.get(id=tagihan_id, siswa=request.user.siswa)
        
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
    is_production=False,
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


@csrf_exempt # WAJIB, karena notifikasi ini datang dari luar
def webhook_midtrans(request):
    if request.method == 'POST':
        try: # <-- TRY 1: Untuk menangkap error JSON
            # 1. Ambil body notifikasi dalam format JSON
            body = json.loads(request.body)
            transaction_status = body.get('transaction_status')
            order_id = body.get('order_id')
            transaction_id = body.get('transaction_id') # ID dari Midtrans
            
            print(f"WEBHOOK DITERIMA: Order ID {order_id}, Status {transaction_status}")

            # 2. Cek status transaksi
            tagihan_id = None
            try: # <-- TRY 2: Untuk menangkap error database/parsing
                # 3. Parsing order_id untuk dapatkan tagihan_id
                # Asumsi format order_id: "SPP-TAGIHAN_ID-UUID"
                tagihan_id = order_id.split('-')[1]
                tagihan = Tagihan.objects.get(id=tagihan_id)

                # 4. Handle berdasarkan status
                if transaction_status == 'settlement':
                    # Pembayaran LUNAS
                    if tagihan.status != 'LUNAS':
                        tagihan.status = 'LUNAS'
                        tagihan.save()

                        # Buat catatan Pembayaran HANYA jika belum ada
                        Pembayaran.objects.update_or_create(
                            tagihan=tagihan,
                            defaults={
                                'jumlah_bayar': tagihan.jumlah,
                                'id_transaksi_gateway': transaction_id,
                                'metode_pembayaran': body.get('payment_type')
                            }
                        )
                        print(f"Tagihan {tagihan_id} berhasil di-update ke LUNAS.")

                elif transaction_status == 'pending':
                    # Pembayaran Menunggu (misal: Bank Transfer)
                    if tagihan.status == 'BELUM_LUNAS':
                        tagihan.status = 'PENDING'
                        tagihan.save()
                        print(f"Tagihan {tagihan_id} di-update ke PENDING.")

                elif transaction_status in ['expire', 'cancel', 'deny']:
                    # Pembayaran Gagal, Batal, atau Kadaluarsa
                    if tagihan.status == 'PENDING' or tagihan.status == 'BELUM_LUNAS':
                        tagihan.status = 'KADALUARSA'
                        tagihan.save()
                        print(f"Tagihan {tagihan_id} di-update ke KADALUARSA.")

                # 5. Kirim balasan "OK" ke Midtrans
                return HttpResponse(status=200)

            except (Tagihan.DoesNotExist, IndexError, ValueError) as e:
                print(f"Error: Tagihan tidak ditemukan atau order_id tidak valid. Order ID: {order_id}. Error: {e}")
                return HttpResponse(status=404) # Not Found

        except json.JSONDecodeError: # <-- EXCEPT yang hilang untuk TRY 1
            print("Error: JSON tidak valid dari Midtrans")
            return HttpResponse(status=400) # Bad Request
    
    # Jika request bukan POST
    print("Webhook hanya mengizinkan metode POST")
    return HttpResponse(status=405) # Method Not Allowed