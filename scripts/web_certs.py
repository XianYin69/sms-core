#!/usr/bin/env python3
"""web_certs.py — 自签 TLS 指纹证书：ECDSA P-256、CN=localhost＋SAN(localhost/127.0.0.1)、825 天，存 <SMS_HOME>/shell/tls/{cert.pem,key.pem}（私钥不出本机目录）；指纹＝sha256(证书 DER) hex，供网页壳/对外端口本地信任钉选与服务端证书核验。用法：python -B web_certs.py ensure|fingerprint|status|rotate。"""
import os, sys, ssl, json, hashlib, datetime, ipaddress
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_home
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID
def paths():
    d = os.path.join(resolve_home.ensure(), "shell", "tls"); return os.path.join(d, "cert.pem"), os.path.join(d, "key.pem")
def _build():
    key = ec.generate_private_key(ec.SECP256R1()); now = datetime.datetime.now(datetime.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SMS net shell")])
    cert = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()) \
        .not_valid_before(now - datetime.timedelta(hours=1)).not_valid_after(now + datetime.timedelta(days=825)) \
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]), critical=False) \
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(key, hashes.SHA256())
    return key, cert
def ensure(force=False):
    cp, kp = paths()
    if os.path.exists(cp) and not force: return cp, kp
    key, cert = _build(); os.makedirs(os.path.dirname(cp), exist_ok=True)
    open(kp, "wb").write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    open(cp, "wb").write(cert.public_bytes(serialization.Encoding.PEM))
    try: os.chmod(kp, 0o600)
    except OSError: pass
    return cp, kp
def _cert():
    cp, _ = ensure(); return x509.load_pem_x509_certificate(open(cp, "rb").read())
def fpr(): return hashlib.sha256(_cert().public_bytes(serialization.Encoding.DER)).hexdigest()
def context():
    cp, kp = ensure(); ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(certfile=cp, keyfile=kp); ctx.minimum_version = ssl.TLSVersion.TLSv1_2; return ctx
def status():
    cp, kp = paths(); ok = os.path.exists(cp); c = _cert() if ok else None
    return {"cert": cp, "exists": ok, "fingerprint": fpr() if ok else None, "not_after": str(c.not_valid_after_utc) if c else None}
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    print(json.dumps(status(), ensure_ascii=False) if cmd == "status" else (ensure(True) and "rotated") if cmd == "rotate" else ensure()[0] if cmd == "ensure" else fpr())
