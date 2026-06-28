PLANNER_PROMPT_TEMPLATE = """
You are an expert in video production, instructional design, and JEE physics education. Please design a high-quality video to explain the solution to a physics problem.

Video Overview:

Question: {question}
Solution Steps: {solution}

Scene Breakdown:

Plan individual scenes that explain this physics solution. For each scene provide:

- Scene Title: Short, descriptive title (2-5 words).
- Scene Purpose: What physics concept or solution step does this scene explain?
- Scene Description: Detailed description of visual content, equations, diagrams.
- Scene Layout: Detailed description of the spatial layout concept. Consider equations, diagrams, vectors, graphs. Ensure minimum spacing between elements.
- Narration Script: CONCISE teacher-style narration (20-40 words max per scene). Like a teacher pointing to a board, guide attention to key elements without reading everything displayed.

Please generate the scene plan in this format:

SCENE PLAN BEGIN:
[Scene 1]
Title: Problem Statement and Approach
Purpose: To present the question and identify key physics concepts
Description: Display the question text, then highlight key physics concepts and relevant formulas needed for solution.
Layout: Question at top, then split screen: left side shows list of relevant concepts, right side shows key formulas.
Narration: "Here's our problem. Notice we're dealing with circular motion and forces. We'll use Newton's second law and centripetal force concepts."

[Scene 2]
...continue with solution steps...

SCENE PLAN END:

CRITICAL NARRATION GUIDELINES:
1. Keep narration BRIEF (20-40 words per scene) - like a teacher highlighting key points
2. FIRST SCENE must start with a warm teacher introduction: "Hello! Today we will learn about..." or "Welcome students! Let's understand..."
3. LAST SCENE must end with encouraging conclusion: "I hope you understand the solution now!" or "That's how we solve it. I hope this was clear!"
4. DO NOT read equations or text displayed on screen
5. Point out what's IMPORTANT: "Notice the key term here" or "This step is crucial because..."
6. Guide attention: "Look at the force diagram" or "See how energy is conserved"
7. Explain WHY, not WHAT: "We use this formula because..." not "The formula is..."
8. Each scene's narration should match its visual content duration (3-8 seconds of speech)
9. Avoid long sentences - use short, clear phrases
10. Focus on insights and connections, not descriptions

VIDEO STRUCTURE GUIDELINES:
1. Start with clear problem statement
2. Break solution into logical steps (6-12 scenes total)
3. Emphasize visual representations (diagrams, graphs, vectors)
4. Highlight key equations and calculations
5. Include brief explanations of physics concepts
6. Show clear connections between steps
7. End with solution verification and key takeaways

Create scenes that help students understand both HOW to solve the problem and WHY each step works. Remember: Visual content teaches, narration guides attention."""

def get_planner_prompt(question, solution):
    """Generate a prompt for the planner agent."""
    return PLANNER_PROMPT_TEMPLATE.format(
        question=question,
        solution=solution
    )