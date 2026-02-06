
import numpy as np
from scipy import stats
import math

@router.get("/efficiency_analysis")
async def get_efficiency_analysis(course_id: int, db: Session = Depends(get_db)):
    """
    Paas (1993) Teaching Efficiency Analysis
    Calculates Z-scores for performance and mental effort, efficiency scores,
    and performs statistical tests (Kruskal-Wallis + Dunn's)
    """
    # Get all quiz results for this course
    results = db.query(QuizResult).filter(
        QuizResult.course_id == course_id,
        QuizResult.is_deleted == False
    ).all()
    
    if len(results) < 2:
        return {"error": "Insufficient data. Need at least 2 quiz results."}
    
    # Extract data
    data_points = []
    for result in results:
        user = db.query(User).filter(User.id == result.user_id).first()
        if not user:
            continue
            
        # Calculate quiz score percentage
        total_score = result.translation_correct + result.sentence_avg
        max_possible = result.translation_total + 5.0  # 5 is max sentence score
        quiz_score_pct = (total_score / max_possible * 100) if max_possible > 0 else 0
        
        # Get NASA mental demand (R)
        nasa_mental = result.nasa_mental or 50  # Default if missing
        
        data_points.append({
            "user_id": user.id,
            "name": user.name or f"User {user.id}",
            "group": result.group or "Unknown",
            "quiz_score": quiz_score_pct,
            "nasa_mental": nasa_mental
        })
    
    if len(data_points) < 2:
        return {"error": "Insufficient valid data after processing."}
    
    # Calculate grand mean and SD for Z-score standardization
    all_scores = [p["quiz_score"] for p in data_points]
    all_nasa = [p["nasa_mental"] for p in data_points]
    
    M_performance = np.mean(all_scores)
    SD_performance = np.std(all_scores, ddof=1)  # Sample std
    M_effort = np.mean(all_nasa)
    SD_effort = np.std(all_nasa, ddof=1)
    
    # Avoid division by zero
    if SD_performance == 0:
        SD_performance = 1
    if SD_effort == 0:
        SD_effort = 1
    
    # Calculate Z-scores and efficiency for each student
    for point in data_points:
        Z_P = (point["quiz_score"] - M_performance) / SD_performance
        Z_R = (point["nasa_mental"] - M_effort) / SD_effort
        E = (Z_P - Z_R) / math.sqrt(2)
        
        point["Z_P"] = round(Z_P, 3)
        point["Z_R"] = round(Z_R, 3)
        point["E"] = round(E, 3)
    
    # Calculate group averages
    groups = {}
    for point in data_points:
        grp = point["group"]
        if grp not in groups:
            groups[grp] = {"Z_P": [], "Z_R": [], "E": []}
        groups[grp]["Z_P"].append(point["Z_P"])
        groups[grp]["Z_R"].append(point["Z_R"])
        groups[grp]["E"].append(point["E"])
    
    group_averages = []
    for grp, values in groups.items():
        group_averages.append({
            "group": grp,
            "Z_P_mean": round(np.mean(values["Z_P"]), 3),
            "Z_R_mean": round(np.mean(values["Z_R"]), 3),
            "E_mean": round(np.mean(values["E"]), 3),
            "count": len(values["E"])
        })
    
    # Statistical tests - Kruskal-Wallis on efficiency scores
    statistical_results = {}
    if len(groups) >= 2:
        # Prepare data for Kruskal-Wallis
        efficiency_by_group = [values["E"] for values in groups.values()]
        
        try:
            # Kruskal-Wallis test
            H, p_kw = kruskal(*efficiency_by_group)
            statistical_results["kruskal_wallis"] = {
                "H": round(H, 4),
                "p": round(p_kw, 4),
                "significant": p_kw < 0.05
            }
            
            # Dunn's post-hoc test if significant
            if p_kw < 0.05:
                # Prepare data for Dunn's test
                df_for_dunn = []
                for grp, values in groups.items():
                    for e_score in values["E"]:
                        df_for_dunn.append({"group": grp, "efficiency": e_score})
                
                df_dunn = pd.DataFrame(df_for_dunn)
                dunn_result = sp.posthoc_dunn(df_dunn, val_col='efficiency', group_col='group', p_adjust='bonferroni')
                
                # Convert to readable format
                dunn_comparisons = []
                group_names = list(groups.keys())
                for i, grp1 in enumerate(group_names):
                    for grp2 in group_names[i+1:]:
                        p_val = dunn_result.loc[grp1, grp2]
                        dunn_comparisons.append({
                            "group1": grp1,
                            "group2": grp2,
                            "p_value": round(p_val, 4),
                            "significant": p_val < 0.05
                        })
                
                statistical_results["dunn_test"] = dunn_comparisons
        except Exception as e:
            statistical_results["error"] = str(e)
    
    # Descriptive statistics
    statistical_results["descriptive"] = {
        "M_performance": round(M_performance, 2),
        "SD_performance": round(SD_performance, 2),
        "M_effort": round(M_effort, 2),
        "SD_effort": round(SD_effort, 2),
        "total_students": len(data_points),
        "num_groups": len(groups)
    }
    
    return {
        "individual_points": data_points,
        "group_averages": group_averages,
        "statistics": statistical_results
    }
