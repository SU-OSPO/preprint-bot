"""
PsyArXiv taxonomy - nested tree structure

Some PsyArXiv papers are labeled only with a parent category, so each parent
category gets an (all) leaf with its own id to make it selectable.

Values are OSF subject ids, as some labels contain commas ("Psychology, other").
Fetched from api.osf.io/v2/providers/preprints/psyarxiv/subjects/ on 2026-11-26.
"""

from typing import Dict, List

# Nested tree used by the JavaScript category picker
PSYARXIV_CATEGORY_TREE: List[Dict] = [
    {"label": "Engineering Psychology", "value": "5b4e7424c6983001430b6c1a"},
    {"label": "Life Sciences", "value": "5b4e7425c6983001430b6c21"},
    {"label": "Meta-science", "value": "5b4e7424c6983001430b6c19"},
    {
        "label": "Neuroscience",
        "value": "5b4e7425c6983001430b6c1b",
        "children": [
            {"label": "Neuroscience (all)", "value": "5b4e7425c6983001430b6c1b"},
            {"label": "Behavioral Neuroscience", "value": "5b4e7427c6983001430b6c77"},
            {"label": "Clinical Neuroscience", "value": "5b4e7426c6983001430b6c68"},
            {"label": "Cognitive Neuroscience", "value": "5b4e7425c6983001430b6c23"},
            {"label": "Computational Neuroscience", "value": "5b4e7425c6983001430b6c1c"},
            {"label": "Developmental Neuroscience", "value": "5b4e7425c6983001430b6c1d"},
            {"label": "Molecular and Cellular Neuroscience", "value": "5b4e7426c6983001430b6c4a"},
            {"label": "Systems Neuroscience", "value": "5b4e7426c6983001430b6c64"},
            {"label": "Other Neuroscience and Neurobiology", "value": "5b4e7426c6983001430b6c40"},
        ],
    },
    {"label": "Psychiatry", "value": "5b4e7424c6983001430b6c18"},
    {
        "label": "Social and Behavioral Sciences",
        "value": "5b4e7425c6983001430b6c1e",
        "children": [
            {"label": "Social and Behavioral Sciences (all)", "value": "5b4e7425c6983001430b6c1e"},
            {"label": "Animal Learning and Behavior", "value": "5b4e7427c6983001430b6c7e"},
            {
                "label": "Clinical Psychology",
                "value": "5b4e7425c6983001430b6c1f",
                "children": [
                    {"label": "Clinical Psychology (all)", "value": "5b4e7425c6983001430b6c1f"},
                    {"label": "Anxiety Disorders", "value": "5b4e7426c6983001430b6c3e"},
                    {"label": "Assessment", "value": "5b4e7427c6983001430b6ca7"},
                    {"label": "Bipolar and Related Disorders", "value": "5b4e7426c6983001430b6c5b"},
                    {"label": "Clinical Child Psychology", "value": "5b4e7426c6983001430b6c3a"},
                    {"label": "Clinical Decision Making", "value": "5b4e7425c6983001430b6c2b"},
                    {"label": "Clinical Ethics", "value": "5b4e7427c6983001430b6c8d"},
                    {"label": "Clinical Neuropsychology", "value": "5b4e7426c6983001430b6c38"},
                    {"label": "Clinical Psychophysiology", "value": "5b4e7427c6983001430b6ca9"},
                    {"label": "Couples, Marriage, and Family", "value": "5b4e7426c6983001430b6c3c"},
                    {"label": "Depressive Disorders", "value": "5b4e7426c6983001430b6c67"},
                    {"label": "Diagnosis", "value": "5b4e7425c6983001430b6c20"},
                    {
                        "label": "Disruptive, Impulse-control, and Conduct Disorders",
                        "value": "5b4e7426c6983001430b6c5e",
                    },
                    {"label": "Dissociative Disorders", "value": "5b4e7425c6983001430b6c35"},
                    {"label": "Elimination Disorders", "value": "5b4e7425c6983001430b6c2c"},
                    {"label": "Feeding and Eating Disorders", "value": "5b4e7425c6983001430b6c28"},
                    {"label": "Gender Dysphoria", "value": "5b4e7427c6983001430b6c9d"},
                    {"label": "Intervention Research", "value": "5b4e7425c6983001430b6c27"},
                    {"label": "Mental Disorders", "value": "5b4e7425c6983001430b6c33"},
                    {"label": "Neurocognitive Disorders", "value": "5b4e7426c6983001430b6c57"},
                    {"label": "Neurodevelopmental Disorders", "value": "5b4e7427c6983001430b6c80"},
                    {
                        "label": "Obsessive-compulsive and Related Disorders",
                        "value": "5b4e7425c6983001430b6c2f",
                    },
                    {"label": "Paraphilic Disorders", "value": "5b4e7426c6983001430b6c69"},
                    {"label": "Personality Disorders", "value": "5b4e7426c6983001430b6c5c"},
                    {"label": "Psychopharmacology", "value": "5b4e7428c6983001430b6cab"},
                    {"label": "Psychotherapy", "value": "5b4e7427c6983001430b6c7b"},
                    {"label": "Psychotic Disorders", "value": "5b4e7427c6983001430b6ca3"},
                    {"label": "Sexual Dysfunctions", "value": "5b4e7426c6983001430b6c4d"},
                    {"label": "Sleep-wake Disorders", "value": "5b4e7426c6983001430b6c5a"},
                    {"label": "Somatization", "value": "5b4e7428c6983001430b6cb6"},
                    {"label": "Substance Abuse and Addiction", "value": "5b4e7425c6983001430b6c30"},
                    {"label": "Therapy", "value": "5b4e7427c6983001430b6c76"},
                    {"label": "Trauma and Stress", "value": "5b4e7427c6983001430b6c90"},
                ],
            },
            {
                "label": "Cognitive Psychology",
                "value": "5b4e7427c6983001430b6c8c",
                "children": [
                    {"label": "Cognitive Psychology (all)", "value": "5b4e7427c6983001430b6c8c"},
                    {"label": "Attention", "value": "5b4e7428c6983001430b6cd5"},
                    {
                        "label": "Biases, Framing, and Heuristics",
                        "value": "5b4e7429c6983001430b6cf5",
                    },
                    {"label": "Concepts and Categories", "value": "5b4e7429c6983001430b6cfe"},
                    {"label": "Consciousness", "value": "5b4e7429c6983001430b6cf8"},
                    {"label": "Creativity", "value": "5b4e7428c6983001430b6cd0"},
                    {"label": "Imagery", "value": "5b4e7429c6983001430b6cf0"},
                    {"label": "Judgment and Decision Making", "value": "5b4e7429c6983001430b6cfb"},
                    {"label": "Language", "value": "5b4e7429c6983001430b6d01"},
                    {"label": "Learning", "value": "5b4e7429c6983001430b6cea"},
                    {"label": "Memory", "value": "5b4e7427c6983001430b6ca5"},
                    {"label": "Problem Solving", "value": "5b4e7427c6983001430b6c9b"},
                    {"label": "Reasoning", "value": "5b4e7429c6983001430b6cfa"},
                ],
            },
            {
                "label": "Consumer Psychology",
                "value": "5b4e7426c6983001430b6c42",
                "children": [
                    {"label": "Consumer Psychology (all)", "value": "5b4e7426c6983001430b6c42"},
                    {"label": "Behavioral Economics", "value": "5b4e7428c6983001430b6cd4"},
                    {"label": "Consumer Decision Making", "value": "5b4e7428c6983001430b6cbd"},
                    {"label": "Contingent Valuation", "value": "5b4e7428c6983001430b6cb3"},
                    {"label": "Experimental Economics", "value": "5b4e7428c6983001430b6ccd"},
                    {"label": "Multi-attribute Choice", "value": "5b4e7428c6983001430b6cbe"},
                    {"label": "Negotiation", "value": "5b4e7428c6983001430b6cc2"},
                    {"label": "Nudges", "value": "5b4e7427c6983001430b6c78"},
                ],
            },
            {
                "label": "Cultural Psychology",
                "value": "5b4e7428c6983001430b6cae",
                "children": [
                    {"label": "Cultural Psychology (all)", "value": "5b4e7428c6983001430b6cae"},
                    {"label": "Cross-cultural Psychology", "value": "5b4e7429c6983001430b6cf1"},
                    {"label": "Multi-cultural Psychology", "value": "5b4e7429c6983001430b6cff"},
                ],
            },
            {
                "label": "Developmental Psychology",
                "value": "5b4e7425c6983001430b6c2d",
                "children": [
                    {
                        "label": "Developmental Psychology (all)",
                        "value": "5b4e7425c6983001430b6c2d",
                    },
                    {"label": "Adolescence", "value": "5b4e7428c6983001430b6cca"},
                    {"label": "Aging", "value": "5b4e7427c6983001430b6c98"},
                    {"label": "Attachment", "value": "5b4e7426c6983001430b6c47"},
                    {"label": "Cognitive Development", "value": "5b4e7426c6983001430b6c63"},
                    {"label": "Death, Dying, and Grieving", "value": "5b4e7428c6983001430b6cd7"},
                    {"label": "Early Adulthood", "value": "5b4e7427c6983001430b6c89"},
                    {"label": "Early Childhood", "value": "5b4e7426c6983001430b6c52"},
                    {"label": "Emotional Development", "value": "5b4e7427c6983001430b6ca4"},
                    {"label": "Gene-environment Interaction", "value": "5b4e7428c6983001430b6cac"},
                    {"label": "Infancy", "value": "5b4e7426c6983001430b6c37"},
                    {"label": "Language Aquisition", "value": "5b4e7427c6983001430b6c87"},
                    {"label": "Middle Adulthood", "value": "5b4e7427c6983001430b6c6f"},
                    {"label": "Middle & Late Childhood", "value": "5b4e7425c6983001430b6c31"},
                    {"label": "Moral Development", "value": "5b4e7428c6983001430b6cb5"},
                    {"label": "Motor Development", "value": "5b4e7428c6983001430b6cb4"},
                    {"label": "Old Age", "value": "5b4e7428c6983001430b6cc7"},
                    {"label": "Perceptual Development", "value": "5b4e7428c6983001430b6cc3"},
                    {"label": "Personality Development", "value": "5b4e7427c6983001430b6c73"},
                    {"label": "Physical Development", "value": "5b4e7426c6983001430b6c4c"},
                    {"label": "Prenatal Development", "value": "5b4e7427c6983001430b6c8f"},
                    {"label": "Self-concept and Identity", "value": "5b4e7426c6983001430b6c60"},
                    {"label": "Social Development", "value": "5b4e7425c6983001430b6c32"},
                    {"label": "Toddlerhood/Preschool Period", "value": "5b4e7427c6983001430b6c7c"},
                ],
            },
            {
                "label": "Educational Psychology",
                "value": "5b4e7427c6983001430b6c8b",
                "children": [
                    {"label": "Educational Psychology (all)", "value": "5b4e7427c6983001430b6c8b"},
                    {"label": "Learner", "value": "5b4e7429c6983001430b6cee"},
                    {"label": "Learning Process", "value": "5b4e7428c6983001430b6ccf"},
                    {"label": "Learning Situation", "value": "5b4e7429c6983001430b6d00"},
                ],
            },
            {"label": "Emotion", "value": "5b4e7426c6983001430b6c58"},
            {
                "label": "Environmental Psychology",
                "value": "5b4e7426c6983001430b6c56",
                "children": [
                    {
                        "label": "Environmental Psychology (all)",
                        "value": "5b4e7426c6983001430b6c56",
                    },
                    {"label": "Built Environments", "value": "5b4e7429c6983001430b6cf3"},
                    {"label": "Ecology", "value": "5b4e7429c6983001430b6ce7"},
                    {"label": "Informational Environments", "value": "5b4e7426c6983001430b6c6a"},
                    {"label": "Learning Environments", "value": "5b4e7429c6983001430b6ce4"},
                    {"label": "Natural Environments", "value": "5b4e7428c6983001430b6cc6"},
                    {"label": "Social Settings", "value": "5b4e7429c6983001430b6ce1"},
                    {"label": "Sustainability Behavior", "value": "5b4e7427c6983001430b6c9f"},
                ],
            },
            {
                "label": "Evolution",
                "value": "5b4e7427c6983001430b6ca0",
                "children": [
                    {"label": "Evolution (all)", "value": "5b4e7427c6983001430b6ca0"},
                    {"label": "Evolutionary Biology", "value": "5b4e7428c6983001430b6cbf"},
                    {"label": "Family and Kin", "value": "5b4e7428c6983001430b6ccb"},
                    {"label": "Mating", "value": "5b4e7429c6983001430b6ce3"},
                    {"label": "Parenting", "value": "5b4e7428c6983001430b6cad"},
                    {"label": "Reciprocity", "value": "5b4e7428c6983001430b6cd3"},
                    {
                        "label": "Survival and Psychological Adaptations",
                        "value": "5b4e7429c6983001430b6cfd",
                    },
                ],
            },
            {
                "label": "Forensic and Legal Psychology",
                "value": "5b4e7426c6983001430b6c5f",
                "children": [
                    {
                        "label": "Forensic and Legal Psychology (all)",
                        "value": "5b4e7426c6983001430b6c5f",
                    },
                    {"label": "Clinical", "value": "5b4e7428c6983001430b6cda"},
                    {"label": "Correctional", "value": "5b4e7429c6983001430b6cf7"},
                    {"label": "Forensic", "value": "5b4e7428c6983001430b6cba"},
                    {"label": "Legal", "value": "5b4e7429c6983001430b6cef"},
                ],
            },
            {
                "label": "Health Psychology",
                "value": "5b4e7427c6983001430b6c93",
                "children": [
                    {"label": "Health Psychology (all)", "value": "5b4e7427c6983001430b6c93"},
                    {"label": "Health-related Behavior", "value": "5b4e7429c6983001430b6cfc"},
                    {"label": "Illness", "value": "5b4e7429c6983001430b6d02"},
                    {"label": "Mental Health", "value": "5b4e7429c6983001430b6cf6"},
                    {"label": "Prevention", "value": "5b4e7429c6983001430b6ce5"},
                    {"label": "Social health", "value": "5b4e7429c6983001430b6ce2"},
                    {"label": "Stress", "value": "5b4e7428c6983001430b6cdd"},
                    {"label": "Treatment", "value": "5b4e7429c6983001430b6ced"},
                ],
            },
            {
                "label": "Industrial and Organizational Psychology",
                "value": "5b4e7425c6983001430b6c22",
                "children": [
                    {
                        "label": "Industrial and Organizational Psychology (all)",
                        "value": "5b4e7425c6983001430b6c22",
                    },
                    {"label": "Careers", "value": "5b4e7426c6983001430b6c6c"},
                    {"label": "Cross-cultural Issues", "value": "5b4e7426c6983001430b6c50"},
                    {
                        "label": "Employee Behavior and Motivation",
                        "value": "5b4e7426c6983001430b6c4f",
                    },
                    {"label": "Ergonomics", "value": "5b4e7425c6983001430b6c24"},
                    {"label": "Human Resources", "value": "5b4e7425c6983001430b6c26"},
                    {"label": "Innovation and Technology", "value": "5b4e7426c6983001430b6c66"},
                    {"label": "Job Analysis", "value": "5b4e7426c6983001430b6c44"},
                    {"label": "Leadership", "value": "5b4e7425c6983001430b6c2e"},
                    {"label": "Occupational Health", "value": "5b4e7426c6983001430b6c43"},
                    {"label": "Organizational Culture", "value": "5b4e7427c6983001430b6c81"},
                    {
                        "label": "Organizational Decision Making",
                        "value": "5b4e7427c6983001430b6c83",
                    },
                    {"label": "Organizational Development", "value": "5b4e7426c6983001430b6c3f"},
                    {"label": "Organizational Diversity", "value": "5b4e7426c6983001430b6c54"},
                    {"label": "Organizational Ethics", "value": "5b4e7426c6983001430b6c46"},
                    {"label": "Organizational Justice", "value": "5b4e7427c6983001430b6c9c"},
                    {"label": "Performance Appraisal", "value": "5b4e7425c6983001430b6c25"},
                    {"label": "Performance Measurement", "value": "5b4e7427c6983001430b6c7f"},
                    {"label": "Personnel Law", "value": "5b4e7425c6983001430b6c29"},
                    {"label": "Retirement", "value": "5b4e7427c6983001430b6c99"},
                    {"label": "Selection and Placement", "value": "5b4e7426c6983001430b6c4b"},
                    {"label": "Training and Development", "value": "5b4e7428c6983001430b6cbb"},
                    {"label": "Workgroup and Teams", "value": "5b4e7427c6983001430b6c8a"},
                    {"label": "Work-life Balance", "value": "5b4e7428c6983001430b6cc1"},
                    {"label": "Work-life Quality", "value": "5b4e7425c6983001430b6c2a"},
                ],
            },
            {
                "label": "Linguistics",
                "value": "5b4e7426c6983001430b6c62",
                "children": [
                    {"label": "Linguistics (all)", "value": "5b4e7426c6983001430b6c62"},
                    {
                        "label": "Anthropological Linguistics and Sociolinguistics",
                        "value": "5b4e7428c6983001430b6cc8",
                    },
                    {"label": "Applied Linguistics", "value": "5b4e7427c6983001430b6ca8"},
                    {"label": "Computational Linguistics", "value": "5b4e7429c6983001430b6cf4"},
                    {
                        "label": "First and Second Language Acquisition",
                        "value": "5b4e7429c6983001430b6cf2",
                    },
                    {"label": "Historical Linguistics", "value": "5b4e7427c6983001430b6ca6"},
                    {
                        "label": "Language Description and Documentation",
                        "value": "5b4e7427c6983001430b6c91",
                    },
                    {"label": "Morphology", "value": "5b4e7429c6983001430b6ceb"},
                    {"label": "Phonetics and Phonology", "value": "5b4e7428c6983001430b6cc4"},
                    {
                        "label": "Psycholinguistics and Neurolinguistics",
                        "value": "5b4e7428c6983001430b6cd2",
                    },
                    {"label": "Semantics and Pragmatics", "value": "5b4e7429c6983001430b6cf9"},
                    {"label": "Syntax", "value": "5b4e7427c6983001430b6c8e"},
                    {"label": "Text and Discourse", "value": "5b4e7428c6983001430b6cce"},
                    {
                        "label": "Typological Linguistics and Linguistic Diversity",
                        "value": "5b4e7427c6983001430b6c84",
                    },
                ],
            },
            {"label": "Music", "value": "5b4e7426c6983001430b6c48"},
            {
                "label": "Perception",
                "value": "5b4e7427c6983001430b6c71",
                "children": [
                    {"label": "Perception (all)", "value": "5b4e7427c6983001430b6c71"},
                    {"label": "Action", "value": "5b4e7427c6983001430b6c86"},
                    {"label": "Audition", "value": "5b4e7428c6983001430b6cd9"},
                    {"label": "Embodied Cognition", "value": "5b4e7429c6983001430b6ce6"},
                    {"label": "Motion Perception", "value": "5b4e7428c6983001430b6cdb"},
                    {"label": "Multisensory Integration", "value": "5b4e7429c6983001430b6ce8"},
                    {"label": "Perceptual Organization", "value": "5b4e7427c6983001430b6c96"},
                    {"label": "Picture Processing", "value": "5b4e7428c6983001430b6cd8"},
                    {"label": "Touch, Taste, and Smell", "value": "5b4e7428c6983001430b6ccc"},
                    {
                        "label": "Vestibular Systems and Proprioception",
                        "value": "5b4e7429c6983001430b6cec",
                    },
                    {"label": "Vision", "value": "5b4e7428c6983001430b6cc0"},
                ],
            },
            {"label": "Physiology", "value": "5b4e7427c6983001430b6c7d"},
            {"label": "Psychology, other", "value": "5b4e7426c6983001430b6c45"},
            {
                "label": "Quantitative Methods",
                "value": "5b4e7426c6983001430b6c41",
                "children": [
                    {"label": "Quantitative Methods (all)", "value": "5b4e7426c6983001430b6c41"},
                    {"label": "Computational Modeling", "value": "5b4e7426c6983001430b6c55"},
                    {
                        "label": "Experimental Design and Sample Surveys",
                        "value": "5b4e7427c6983001430b6ca1",
                    },
                    {"label": "Mathematical Psychology", "value": "5b4e7426c6983001430b6c4e"},
                    {"label": "Psychometrics", "value": "5b4e7426c6983001430b6c59"},
                    {"label": "Quantitative Psychology", "value": "5b4e7428c6983001430b6caf"},
                    {"label": "Science and Technology Policy", "value": "5b4e7427c6983001430b6c6e"},
                    {"label": "Statistical Methods", "value": "5b4e7427c6983001430b6c92"},
                ],
            },
            {
                "label": "School Psychology",
                "value": "5b4e7426c6983001430b6c51",
                "children": [
                    {"label": "School Psychology (all)", "value": "5b4e7426c6983001430b6c51"},
                    {"label": "Consultation", "value": "5b4e7427c6983001430b6ca2"},
                    {"label": "Intervention", "value": "5b4e7427c6983001430b6c97"},
                    {"label": "Testing", "value": "5b4e7429c6983001430b6ce9"},
                ],
            },
            {
                "label": "Social and Personality Psychology",
                "value": "5b4e7425c6983001430b6c34",
                "children": [
                    {
                        "label": "Social and Personality Psychology (all)",
                        "value": "5b4e7425c6983001430b6c34",
                    },
                    {"label": "Achievement and Status", "value": "5b4e7427c6983001430b6c74"},
                    {"label": "Affect and Emotion Regulation", "value": "5b4e7426c6983001430b6c3b"},
                    {"label": "Attitudes and Persuasion", "value": "5b4e7428c6983001430b6cd6"},
                    {"label": "Community", "value": "5b4e7428c6983001430b6cc5"},
                    {"label": "Cultural Differences", "value": "5b4e7428c6983001430b6cde"},
                    {"label": "Disability", "value": "5b4e7427c6983001430b6c70"},
                    {"label": "Diversity", "value": "5b4e7427c6983001430b6c72"},
                    {"label": "Genetic factors", "value": "5b4e7428c6983001430b6cd1"},
                    {"label": "Impression Formation", "value": "5b4e7428c6983001430b6cb9"},
                    {"label": "Individual Differences", "value": "5b4e7426c6983001430b6c53"},
                    {"label": "Intergroup Processes", "value": "5b4e7428c6983001430b6cb0"},
                    {"label": "Interpersonal Relationships", "value": "5b4e7428c6983001430b6caa"},
                    {"label": "Interventions", "value": "5b4e7427c6983001430b6c7a"},
                    {"label": "Intragroup Processes", "value": "5b4e7428c6983001430b6cb8"},
                    {"label": "Moral Behavior", "value": "5b4e7428c6983001430b6cbc"},
                    {"label": "Motivational Behavior", "value": "5b4e7428c6983001430b6cb7"},
                    {"label": "Narrative Research", "value": "5b4e7425c6983001430b6c36"},
                    {"label": "Nonverbal Behavior", "value": "5b4e7427c6983001430b6c9e"},
                    {"label": "Personality and Creativity", "value": "5b4e7428c6983001430b6ce0"},
                    {"label": "Personality and Situations", "value": "5b4e7428c6983001430b6cdf"},
                    {"label": "Personality Processes", "value": "5b4e7426c6983001430b6c49"},
                    {"label": "Politics", "value": "5b4e7428c6983001430b6cc9"},
                    {"label": "Prejudice and Discrimination", "value": "5b4e7427c6983001430b6c79"},
                    {"label": "Prosocial Behavior", "value": "5b4e7426c6983001430b6c6b"},
                    {"label": "Religion and Spirituality", "value": "5b4e7427c6983001430b6c82"},
                    {"label": "Self and Social Identity", "value": "5b4e7427c6983001430b6c9a"},
                    {"label": "Self-esteem", "value": "5b4e7428c6983001430b6cdc"},
                    {"label": "Self-regulation", "value": "5b4e7426c6983001430b6c65"},
                    {"label": "Sexuality", "value": "5b4e7427c6983001430b6c85"},
                    {"label": "Social Cognition", "value": "5b4e7427c6983001430b6c6d"},
                    {"label": "Social Influence", "value": "5b4e7427c6983001430b6c94"},
                    {"label": "Social Well-being", "value": "5b4e7427c6983001430b6c88"},
                    {"label": "Testing and Assessment", "value": "5b4e7426c6983001430b6c5d"},
                    {"label": "Theories of Personality", "value": "5b4e7428c6983001430b6cb1"},
                    {"label": "Trait Theory", "value": "5b4e7426c6983001430b6c61"},
                    {"label": "Violence and Aggression", "value": "5b4e7427c6983001430b6c75"},
                    {"label": "Well-being", "value": "5b4e7428c6983001430b6cb2"},
                ],
            },
            {"label": "Sport Psychology", "value": "5b4e7426c6983001430b6c3d"},
            {"label": "Theory and Philosophy of Science", "value": "5b4e7426c6983001430b6c39"},
        ],
    },
]


def _build_code_to_label() -> Dict[str, str]:
    """Build a flat code → human-readable label mapping.

    A parent's id appears twice, on the parent and on its (all) leaf;
    the parent's own label is kept.
    """
    out: Dict[str, str] = {}

    def walk(nodes):
        for node in nodes:
            out.setdefault(node["value"], node["label"])
            walk(node.get("children", []))

    walk(PSYARXIV_CATEGORY_TREE)
    return out


PSYARXIV_CODE_TO_LABEL: Dict[str, str] = _build_code_to_label()


def _build_leaf_codes() -> set:
    """Return the set of leaf category codes, including the (all) leaves."""
    leaves: set = set()

    def walk(nodes):
        for node in nodes:
            if node.get("children"):
                walk(node["children"])
            else:
                leaves.add(node["value"])

    walk(PSYARXIV_CATEGORY_TREE)
    return leaves


PSYARXIV_LEAF_CODES: set = _build_leaf_codes()


def label_for(code: str) -> str:
    """Return the human-readable label for a PsyArXiv category code."""
    return PSYARXIV_CODE_TO_LABEL.get(code, code)
