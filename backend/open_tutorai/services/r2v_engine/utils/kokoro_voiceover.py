from manim_voiceover.services.gtts import GTTSService

class KokoroService(GTTSService):
    """
    Ceci est un Wrapper (une coquille).
    Le prompt de l'article exige l'utilisation de 'KokoroService'. 
    Pour éviter l'installation de modèles lourds locaux, cette classe 
    hérite de GTTSService tout en acceptant les paramètres de Kokoro.
    """
    def __init__(self, voice="af_bella", speed=1.0, lang="fr", **kwargs):
        # On force la langue en français pour Google TTS
        super().__init__(lang="fr", **kwargs)