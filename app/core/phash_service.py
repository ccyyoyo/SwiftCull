import logging
import os
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    log.warning("OpenCV not available - pHash disabled")

_HASH_SIZE = 8          # 8x8 DCT block → 64-bit hash
_DCT_SIZE = 32          # resize target before DCT
_HEX_CHARS = _HASH_SIZE * _HASH_SIZE // 4   # 16 hex chars per 64 bits


class PHashService:
    """Stateless service for DCT-based perceptual hashing and similarity grouping."""

    def compute_hash(self, root_path: str, relative_path: str) -> Optional[str]:
        """Return 16-char hex pHash string, or None on failure."""
        if not _CV2_AVAILABLE:
            return None
        abs_path = os.path.join(root_path, relative_path)
        try:
            from app.core.image_io import read_image_color
            img = read_image_color(abs_path)
            if img is None:
                return None
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (_DCT_SIZE, _DCT_SIZE), interpolation=cv2.INTER_AREA)
            float_img = np.float32(resized)
            dct = cv2.dct(float_img)
            # Take top-left 8×8 block (low-frequency components)
            dct_block = dct[:_HASH_SIZE, :_HASH_SIZE]
            mean = dct_block.mean()
            bits = (dct_block > mean).flatten()
            # Pack 64 bits into a 16-char hex string
            value = int(np.packbits(bits).tobytes().hex(), 16)
            return f"{value:016x}"
        except Exception as e:
            log.debug("Error computing pHash for %s: %s", relative_path, e)
            return None

    @staticmethod
    def hamming_distance(hash_a: str, hash_b: str) -> int:
        """Return bit-level Hamming distance between two 16-char hex hashes."""
        diff = int(hash_a, 16) ^ int(hash_b, 16)
        return bin(diff).count("1")

    @staticmethod
    def group_by_similarity(
        hashes: Dict[int, str],
        threshold: int = 10,
    ) -> List[List[int]]:
        """
        Group photo IDs where any pair within a group is within `threshold` Hamming bits.
        Uses Union-Find for transitive closure. Returns only groups with ≥ 2 members.
        """
        ids = list(hashes.keys())
        n = len(ids)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            parent[find(x)] = find(y)

        hash_values = [hashes[i] for i in ids]
        for i in range(n):
            for j in range(i + 1, n):
                if PHashService.hamming_distance(hash_values[i], hash_values[j]) <= threshold:
                    union(i, j)

        from collections import defaultdict
        clusters: Dict[int, List[int]] = defaultdict(list)
        for i in range(n):
            clusters[find(i)].append(ids[i])

        return [members for members in clusters.values() if len(members) >= 2]
