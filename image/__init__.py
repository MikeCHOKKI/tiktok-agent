"""Pipeline de generation et post-processing d'images pour tiktok-agent.

Modules disponibles :
- router : Routage vers le bon generateur selon le type de visuel
- thumbnail : Generation de miniatures (SDXL Turbo)
- background : Generation de fonds (Stable Diffusion 2.1)
- text_visual : Generation de visuels texte (100% Pillow, sans API)
- illustration : Generation d'illustrations (Kandinsky 2.2)
- postprocessor : Post-processing (recadrage, watermark, optimisation)
"""

from image.router import ImageRouter

__all__ = ["ImageRouter"]
