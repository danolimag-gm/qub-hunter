#!/usr/bin/env python3
"""
Upload les PMTiles du cadastre vers Cloudflare R2.

Prérequis — variables d'environnement :
    R2_ACCOUNT_ID       ID de compte Cloudflare
    R2_ACCESS_KEY_ID    Clé d'accès R2 (dans Dashboard → R2 → Manage API tokens)
    R2_SECRET_ACCESS_KEY
    R2_BUCKET           Nom du bucket (défaut: qub-hunter)

Usage:
    export R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=...
    python upload_r2.py
    python upload_r2.py --region 04
    python upload_r2.py --dry-run
"""
import argparse
import os
import sys
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
    from tqdm import tqdm
except ImportError:
    print("Dépendances manquantes. Exécutez :\n  pip install boto3 tqdm", file=sys.stderr)
    sys.exit(1)

TILES_DIR = Path(__file__).parent.parent / "data" / "pmtiles"

REGIONS = {
    "01": "Bas-Saint-Laurent",
    "02": "Saguenay-Lac-Saint-Jean",
    "03": "Capitale-Nationale",
    "04": "Mauricie",
    "05": "Estrie",
    "06": "Montreal",
    "07": "Outaouais",
    "08": "Abitibi-Temiscamingue",
    "09": "Cote-Nord",
    "10": "Nord-du-Quebec",
    "11": "Gaspesie-Iles-de-la-Madeleine",
    "12": "Chaudiere-Appalaches",
    "13": "Laval",
    "14": "Lanaudiere",
    "15": "Laurentides",
    "16": "Monteregie",
    "17": "Centre-du-Quebec",
}


def get_r2_client(account_id: str, key_id: str, secret: str):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name="auto",
    )


def upload_file(client, bucket: str, local: Path, key: str, dry_run: bool) -> bool:
    size_mb = local.stat().st_size / 1_048_576
    if dry_run:
        print(f"  [dry-run] {local.name} ({size_mb:.1f} Mo) → s3://{bucket}/{key}")
        return True

    class ProgressBar(tqdm):
        def __call__(self, bytes_transferred):
            self.update(bytes_transferred - self.n)

    with ProgressBar(
        desc=local.name, total=local.stat().st_size, unit="B", unit_scale=True
    ) as bar:
        try:
            client.upload_file(
                str(local),
                bucket,
                key,
                ExtraArgs={"ContentType": "application/octet-stream"},
                Callback=bar,
            )
        except (BotoCoreError, ClientError) as e:
            print(f"\n  ✗ Erreur upload : {e}", file=sys.stderr)
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Upload les PMTiles vers Cloudflare R2")
    parser.add_argument("--region", metavar="CODE_OU_ALL", default="all",
                        help="Code région (ex: 04) ou 'all' (défaut)")
    parser.add_argument("--bucket", default=os.getenv("R2_BUCKET", "qub-hunter"),
                        help="Nom du bucket R2 (défaut: qub-hunter ou $R2_BUCKET)")
    parser.add_argument("--prefix", default="cadastre/",
                        help="Préfixe de chemin dans le bucket (défaut: cadastre/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simule l'upload sans rien envoyer")
    args = parser.parse_args()

    account_id = os.getenv("R2_ACCOUNT_ID")
    key_id     = os.getenv("R2_ACCESS_KEY_ID")
    secret     = os.getenv("R2_SECRET_ACCESS_KEY")

    if not all([account_id, key_id, secret]) and not args.dry_run:
        print("✗ Variables d'environnement manquantes :", file=sys.stderr)
        print("  export R2_ACCOUNT_ID=<votre-account-id>")
        print("  export R2_ACCESS_KEY_ID=<votre-key-id>")
        print("  export R2_SECRET_ACCESS_KEY=<votre-secret>")
        sys.exit(1)

    targets = list(REGIONS.keys()) if args.region == "all" else [args.region.zfill(2)]
    files = [(TILES_DIR / f"cadastre_{code}.pmtiles", code) for code in targets]
    files = [(p, c) for p, c in files if p.exists()]

    if not files:
        print("✗ Aucun PMTiles trouvé. Exécutez d'abord generate_pmtiles.py", file=sys.stderr)
        sys.exit(1)

    client = None if args.dry_run else get_r2_client(account_id, key_id, secret)

    print(f"\n→ Upload vers R2 bucket '{args.bucket}' (préfixe: {args.prefix})")
    print(f"  {len(files)} fichier(s) à uploader\n")

    success, failed = [], []
    for local, code in files:
        key = f"{args.prefix}cadastre_{code}.pmtiles"
        ok = upload_file(client, args.bucket, local, key, args.dry_run)
        (success if ok else failed).append(code)

    print(f"\n✓ {len(success)}/{len(files)} fichiers uploadés")
    if failed:
        print(f"  ✗ Échecs : {', '.join(failed)}")

    if success and not args.dry_run:
        print(f"\n  URLs publiques (si bucket public) :")
        for _, code in [(p, c) for p, c in files if c in success]:
            print(f"  https://<votre-domaine-r2>/{args.prefix}cadastre_{code}.pmtiles")
        print("\n  Copiez ces URLs dans qub-hunter-phase07.html (CADASTRE_PMTILES_BASE)")


if __name__ == "__main__":
    main()
