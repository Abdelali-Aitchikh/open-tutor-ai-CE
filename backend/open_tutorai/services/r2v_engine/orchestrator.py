import os
import sys
import uuid
import logging
from pathlib import Path

# ==============================================================================
# HACK D'ENCAPSULATION ARCHITECTURALE
# ==============================================================================
# 1. On indique à Python que le dossier 'r2v_engine' est une racine autonome.
current_engine_dir = Path(__file__).parent.resolve()
if str(current_engine_dir) not in sys.path:
    sys.path.insert(0, str(current_engine_dir))

# 2. IMPORTS SANS LE POINT DEVANT ! 
# (Grâce au hack ci-dessus, Python trouvera les dossiers 'agents' et 'manim_handler')
try:
    from agents.physics_solution_agent import PhysicsSolutionAgent
    from agents.planner_agent import PlannerAgent
    from agents.coding_agent import CodingAgent
    from manim_handler.executor import ManimExecutor
except ModuleNotFoundError as e:
    raise RuntimeError(
        f"Erreur fatale d'importation : {e}\n"
        "-> SOLUTION : Vérifie que tu as bien créé un fichier vide '__init__.py' "
        "à l'intérieur de tes dossiers 'agents', 'utils' et 'manim_handler'."
    )
# ==============================================================================

log = logging.getLogger(__name__)

class ManimPipelineOrchestrator:
    def __init__(self, temp_dir: Path, llm_client):
        self.temp_dir = temp_dir
        self.llm_client = llm_client
        
        # Initialisation des agents de ton dossier MANIM
        self.physics_agent = PhysicsSolutionAgent()
        self.planner_agent = PlannerAgent()
        self.coding_agent = CodingAgent(
            use_rag=True, 
            context_learning_path=str(current_engine_dir / "examples/context_learning")
        )
        self.executor = ManimExecutor(output_dir=str(temp_dir))

    def run_pipeline(self, question: str, callback=None) -> str:
        """
        Exécute tout le pipeline de ton dossier MANIM.
        `callback` permet d'envoyer des messages en temps réel au frontend SSE.
        """
        def emit(progress, msg):
            if callback: callback(progress, msg)

        try:
            emit(10, "🧠 Étape 1: L'Agent Physique résout le problème...")
            solution = self.physics_agent.solve_question(question)

            emit(25, "🎬 Étape 2: L'Agent Scénariste prépare le storyboard...")
            scene_plan = self.planner_agent.generate_plan(question, solution)

            emit(40, "💻 Étape 3: L'Agent Codeur génère le script Manim...")
            manim_code = self.coding_agent.generate_code(question, solution, scene_plan)

            emit(60, "⚙️ Étape 4: Exécution de Manim et auto-correction...")
            
            # Ton système de boucle d'erreur à 5 tentatives
            success = False
            attempts = 0
            while attempts < 3 and not success:
                success, error_msg, video_paths = self.executor.execute_code(
                    manim_code, 
                    filename=str(self.temp_dir / "scene.py")
                )
                if not success:
                    attempts += 1
                    emit(60 + attempts*5, f"⚠️ Erreur Manim, l'IA corrige le code (Essai {attempts}/3)...")
                    manim_code = self.coding_agent.fix_code(scene_plan, manim_code, error_msg)

            if not success:
                raise RuntimeError("Échec de la génération Manim après plusieurs tentatives.")

            emit(90, "🎞️ Étape 5: Assemblage de la vidéo...")
            # Code pour assembler ou récupérer la vidéo finale
            final_video_path = str(self.temp_dir / video_paths[0])

            emit(100, "✅ Rendu terminé !")
            return final_video_path

        except Exception as e:
            log.error(f"Pipeline failed: {e}")
            raise e