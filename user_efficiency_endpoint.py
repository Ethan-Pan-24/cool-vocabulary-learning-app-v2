

@router.get("/user_efficiency_plot")
async def get_user_efficiency_plot(course_id: int, user_id: int, db: Session = Depends(get_db)):
    """
    Generate efficiency quadrant scatter plot with USER'S point highlighted
    For user-facing dashboard
    """
    # Get data from efficiency_analysis endpoint
    data = await get_efficiency_analysis(course_id, db)
    
    if "error" in data:
        raise HTTPException(400, data["error"])
    
    # Find user's specific data point
    user_data = None
    for point in data["individual_points"]:
        if point["user_id"] == user_id:
            user_data = point
            break
    
    if not user_data:
        raise HTTPException(404, "User data not found in this course")
    
    # Create plot
    plt.figure(figsize=(12, 10))
    
    # Prepare data for plotting
    df_individual = pd.DataFrame(data["individual_points"])
    df_groups = pd.DataFrame(data["group_averages"])
    
    # Plot individual points (muted)
    palette = sns.color_palette("husl", len(df_groups))
    group_colors = {grp["group"]: palette[i] for i, grp in enumerate(data["group_averages"])}
    
    for grp in df_individual["group"].unique():
        subset = df_individual[df_individual["group"] == grp]
        plt.scatter(subset["Z_R"], subset["Z_P"], 
                   label=f"Group {grp}", 
                   alpha=0.3, s=80,  # More muted
                   color=group_colors.get(grp, 'gray'))
    
    # Plot group averages (medium emphasis)
    for _, row in df_groups.iterrows():
        plt.scatter(row["Z_R_mean"], row["Z_P_mean"], 
                   s=400, marker='D', 
                   edgecolors='black', linewidths=2,
                   color=group_colors.get(row["group"], 'gray'),
                   alpha=0.7,
                   label=f"Group {row['group']} Mean",
                   zorder=10)
    
    # HIGHLIGHT USER'S POINT (MOST PROMINENT)
    plt.scatter(user_data["Z_R"], user_data["Z_P"],
               s=800, marker='*',  # Large star
               edgecolors='red', linewidths=3,
               color='gold',
               label=f'YOU ({user_data["name"]})',
               zorder=20)
    
    # Add text annotation for user's point
    plt.annotate(f'YOU\n({user_data["name"]})',
                xy=(user_data["Z_R"], user_data["Z_P"]),
                xytext=(user_data["Z_R"] + 0.3, user_data["Z_P"] + 0.3),
                fontsize=12, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8),
                arrowprops=dict(arrowstyle='->', lw=2, color='red'))
    
    # Draw E=0 diagonal line (R = P)
    lim = max(abs(df_individual["Z_R"].max()), abs(df_individual["Z_P"].max()), 3)
    plt.plot([-lim, lim], [-lim, lim], 'k--', alpha=0.5, linewidth=2, label='E=0 (R=P)')
    
    # Add quadrant labels
    plt.text(-lim*0.7, lim*0.7, '高效率\nHigh Efficiency\n(低努力·高表現)', 
             ha='center', fontsize=11, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    plt.text(lim*0.7, -lim*0.7, '低效率\nLow Efficiency\n(高努力·低表現)', 
             ha='center', fontsize=11, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
    
    # Formatting
    plt.xlabel('Mental Effort Z-score (R)\n心智努力標準分數', fontsize=13, fontweight='bold')
    plt.ylabel('Learning Performance Z-score (P)\n學習表現標準分數', fontsize=13, fontweight='bold')
    plt.title(f'Your Teaching Efficiency Position\n你的學習效率位置', fontsize=15, fontweight='bold')
    plt.axhline(0, color='gray', linestyle='-', linewidth=0.8, alpha=0.5)
    plt.axvline(0, color='gray', linestyle='-', linewidth=0.8, alpha=0.5)
    plt.grid(alpha=0.3, linestyle='--')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', framealpha=0.9)
    plt.tight_layout()
    
    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    # Encode to base64
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    
    # Determine quadrant and message
    if user_data["E"] > 0:
        if user_data["Z_R"] < 0:
            quadrant = "高效率 (High Efficiency)"
            message = "您在高效率象限！您以較低的心智努力獲得了良好的學習成果。"
        else:
            quadrant = "高表現 (High Performance)"
            message = "您的學習表現良好，但需要較高的心智努力。"
    else:
        if user_data["Z_R"] > 0:
            quadrant = "低效率 (Low Efficiency)"
            message = "您需要很高的心智努力，但學習成果較低。建議調整學習策略。"
        else:
            quadrant = "低表現 (Low Performance)"
            message = "您的心智努力和學習表現都較低。可能需要更多練習。"
    
    return {
        "image": f"data:image/png;base64,{img_base64}",
        "user_data": user_data,
        "quadrant": quadrant,
        "message": message,
        "statistics": data["statistics"]
    }
