import subprocess
import os
import sys
import glob
import shutil
import logging
import re

logger = logging.getLogger(__name__)

class ManimExecutor:
    def __init__(self, output_dir="media"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def execute_code(self, code: str, filename: str = "temp_scene.py"):
        """Exécute le code Manim généré par l'IA avec un système d'interception."""
        file_base_name = os.path.basename(filename).split('.')[0]
        temp_working_dir = os.path.dirname(filename)
        
        # --- NETTOYAGE DU CACHE ---
        cache_dir = os.path.join(temp_working_dir, "media")
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            logger.info("🧹 Cache Manim nettoyé.")

        # ================================================================
        # 🛡️ INTERCEPTEUR DE CODE (ANTI-HALLUCINATIONS)
        # ================================================================
        code = code.replace(
            "from utils.kokoro_voiceover import KokoroService", 
            "from manim_voiceover.services.gtts import GTTSService"
        )
        code = re.sub(r"KokoroService\([^)]*\)", "GTTSService(lang='fr')", code)
        # ================================================================

        # Sauvegarder le code propre dans le fichier
        with open(filename, "w", encoding="utf-8") as f:
            f.write(code)
            
        logger.info(f"Exécution de Manim sur le fichier: {filename}")
        
        # Lancer Manim
        command = [sys.executable, "-m", "manim", "-qm", "-a", filename]
        
        try:
            # 🚨 CORRECTION MAJEURE ICI : cwd=temp_working_dir
            # Force Manim à travailler uniquement dans le dossier temporaire de l'utilisateur !
            process = subprocess.run(command, capture_output=True, text=True, cwd=temp_working_dir)
            
            logger.info(f"\n--- LOGS INTERNES DE MANIM ---\n{process.stdout}\n------------------------------")
            
            if process.returncode != 0:
                error_msg = process.stderr if process.stderr else process.stdout
                logger.error(f"Erreur Manim détectée: {error_msg[-500:]}")
                return False, error_msg, []

            logger.info("Manim a terminé l'exécution. Recherche des fichiers MP4...")
            
            # 🚨 CORRECTION DU CHEMIN DE RECHERCHE (COMPATIBLE WINDOWS)
            search_pattern = os.path.join(temp_working_dir, "media", "videos", file_base_name, "**", "*.mp4")
            video_files = glob.glob(search_pattern, recursive=True)
            
            final_files = []
            for vf in video_files:
                if "partial_movie_files" not in vf:
                    base_name = os.path.basename(vf)
                    dest = os.path.join(self.output_dir, base_name)
                    shutil.copy(vf, dest)
                    final_files.append(base_name)
            
            logger.info(f"Fichiers trouvés et copiés : {final_files}")
            
            # 🚨 SECURITE ANTI-CRASH : Si aucun fichier n'est trouvé malgré le succès
            if not final_files:
                logger.error("Aucune vidéo trouvée. Les fichiers ont dû être sauvegardés ailleurs.")
                return False, "Erreur système: Fichier MP4 introuvable après génération.", []

            return True, "", final_files
            
        except Exception as e:
            logger.error(f"Erreur système critique : {str(e)}")
            return False, str(e), []