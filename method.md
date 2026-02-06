# ==========================================
# 1. 安裝必要套件 (若在 Colab 請取消註解執行)
# ==========================================
!pip install --upgrade scipy scikit-posthocs pandas seaborn matplotlib openpyxl

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from scipy import stats
import scikit_posthocs as sp
import numpy as np
import math

# 設定繪圖風格與字體
sns.set_style("whitegrid")
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

# ==========================================
# ⚙️ PARAMS: 檔案路徑與工作表設定
# ==========================================
FILE_PRE   = '前測flittered 刪掉2年級.xlsx'
FILE_POST  = 'filtered_後測以及使用意願分析 刪掉2年級.xlsx'
FILE_DELAY = 'filtered_延遲後測 刪掉2年級.xlsx'

# 設定四個分組
SHEETS = ['a', 'b', 'c', 'd']

# ==========================================
# 🛠️ 工具函數
# ==========================================
def clean_score(value):
    """清洗分數"""
    if pd.isna(value): return np.nan
    value = str(value).strip()
    if '/' in value:
        try:
            return float(value.split('/')[0].strip())
        except:
            return np.nan
    try:
        return float(value)
    except:
        return np.nan

def print_separator(title):
    print(f"\n{'='*70}")
    print(f"🔹 {title}")
    print(f"{'='*70}")

def format_p_value(p):
    if p < 0.001: return "p < .001"
    return f"p = {p:.4f}"

# ==========================================
# 📊 PART 1, 3, 4, 5: 通用 Kruskal-Wallis
# ==========================================
# 修改點：增加 print_stats 參數，控制是否印出預設統計表
def perform_kruskal_dunn_plot(df, val_col, group_col, title, y_label, ax_box, ax_heat=None, print_stats=True):
    # 1. 計算統計數據
    stats_df = df.groupby(group_col)[val_col].agg(['count', 'mean', 'std', 'median'])
    stats_df = stats_df.reindex(SHEETS)

    # 若 print_stats 為 True 才印出 (Part 4 會設為 False 以避免重複)
    if print_stats:
        print(f"\n>>> Stats for {title}:")
        print(stats_df)

    groups = [df[df[group_col] == g][val_col].values for g in SHEETS]
    valid_groups = [g for g in groups if len(g) > 0]

    if len(valid_groups) < 2:
        ax_box.text(0.5, 0.5, "Insufficient Data", ha='center')
        return

    # Kruskal-Wallis Test
    stat, p_kruskal = stats.kruskal(*valid_groups)

    # 2. 畫 Boxplot
    sns.boxplot(x=group_col, y=val_col, data=df, ax=ax_box, palette="Set2", order=SHEETS)
    sns.stripplot(x=group_col, y=val_col, data=df, ax=ax_box, color='black', alpha=0.5, jitter=True, order=SHEETS)

    color = '#D62728' if p_kruskal < 0.05 else 'black'
    ax_box.set_title(f"{title}\n(Kruskal p={p_kruskal:.3f})", color=color, fontweight='bold')
    ax_box.set_ylabel(y_label)

    # 3. 修改 X 軸標籤：加入 N, Mean, Med, SD
    new_labels = []
    for g in SHEETS:
        if g in stats_df.index and not pd.isna(stats_df.loc[g, 'median']):
            row = stats_df.loc[g]
            label = (f"{g}\n(n={int(row['count'])})\n"
                     f"Mean={row['mean']:.2f}\n"
                     f"Med={row['median']:.2f}\n"
                     f"SD={row['std']:.2f}")
        else:
            label = g
        new_labels.append(label)

    ax_box.set_xticklabels(new_labels)

    # 4. Dunn's Test
    if p_kruskal < 0.05 and ax_heat is not None:
        try:
            dunn_df = sp.posthoc_dunn(df, val_col=val_col, group_col=group_col, p_adjust='bonferroni')
            sns.heatmap(dunn_df, annot=True, cmap="coolwarm_r", vmin=0, vmax=0.05, fmt=".3f",
                        ax=ax_heat, cbar_kws={'label': 'P-value'})
            ax_heat.set_title("Pairwise (Dunn's Test)")
        except:
            ax_heat.text(0.5, 0.5, "Post-hoc Error", ha='center')
    elif ax_heat is not None:
        ax_heat.axis('off')

def analyze_basic_scores():
    print_separator("PART 1: Basic Score Analysis")

    tasks = [
        {'name': 'Pre Test',   'file': FILE_PRE,   'trans_col': 2, 'sent_col': 40},
        {'name': 'Post Test',  'file': FILE_POST,  'trans_col': 2, 'sent_col': 55},
        {'name': 'Delay Test', 'file': FILE_DELAY, 'trans_col': 2, 'sent_col': 40},
    ]

    for task in tasks:
        all_data = []
        for sheet in SHEETS:
            try:
                df = pd.read_excel(task['file'], sheet_name=sheet, header=0, dtype=str)
                trans = df.iloc[:, task['trans_col']].apply(clean_score).dropna()
                for v in trans: all_data.append({'Group': sheet, 'Score': v, 'Type': 'Translation'})
                sent = df.iloc[:, task['sent_col']].apply(clean_score).dropna()
                for v in sent: all_data.append({'Group': sheet, 'Score': v, 'Type': 'Sentence'})
            except Exception as e:
                print(f"⚠️ Warning reading {task['name']} sheet {sheet}: {e}")

        df_plot = pd.DataFrame(all_data)
        if df_plot.empty: continue

        for sub_type in ['Translation', 'Sentence']:
            subset = df_plot[df_plot['Type'] == sub_type]
            if subset.empty: continue

            fig, axes = plt.subplots(1, 2, figsize=(16, 7))
            perform_kruskal_dunn_plot(
                subset, 'Score', 'Group',
                f"{task['name']} - {sub_type}",
                "Score", axes[0], axes[1]
            )
            plt.subplots_adjust(bottom=0.25)
            plt.show()

# ==========================================
# 📈 PART 2: 時間序列分析
# ==========================================
def plot_time_series_with_friedman(ax, df_sub, group_name, subject_name):
    # 1. 計算敘述統計
    desc_stats = df_sub[['Pre', 'Post', 'Delay']].agg(['count', 'std', 'median']).T
    print(f"\n>>> 📊 Descriptive Stats for Group: {group_name} | {subject_name}")
    print(desc_stats.round(3))

    medians = [df_sub['Pre'].median(), df_sub['Post'].median(), df_sub['Delay'].median()]

    q1 = [df_sub['Pre'].quantile(0.25), df_sub['Post'].quantile(0.25), df_sub['Delay'].quantile(0.25)]
    q3 = [df_sub['Pre'].quantile(0.75), df_sub['Post'].quantile(0.75), df_sub['Delay'].quantile(0.75)]

    yerr_low = [m - q for m, q in zip(medians, q1)]
    yerr_high = [q - m for m, q in zip(medians, q3)]
    asymmetric_error = [yerr_low, yerr_high]

    x_points = [0, 1, 2]

    xtick_labels = []
    phases = ['Pre', 'Post', 'Delay']
    for ph in phases:
        n_val = desc_stats.loc[ph, 'count']
        med_val = desc_stats.loc[ph, 'median']
        std_val = desc_stats.loc[ph, 'std']
        xtick_labels.append(f"{ph}\n(n={int(n_val)})\nMed={med_val:.2f}\nSD={std_val:.2f}")

    # 2. Friedman Test
    try:
        stat_fried, p_friedman = stats.friedmanchisquare(df_sub['Pre'], df_sub['Post'], df_sub['Delay'])
    except ValueError:
        p_friedman = 1.0

    # 3. 繪圖
    ax.errorbar(x_points, medians, yerr=asymmetric_error, fmt='-o', capsize=5, lw=2, markersize=8, color='#1f77b4', label=group_name)
    ax.set_xticks(x_points)
    ax.set_xticklabels(xtick_labels)
    ax.set_ylabel("Median Score")

    sig_text = "(*)" if p_friedman < 0.05 else "(ns)"
    title_color = '#D62728' if p_friedman < 0.05 else 'black'
    ax.set_title(f"Group: {group_name} | {subject_name}\nFriedman: {format_p_value(p_friedman)} {sig_text}",
                 fontweight='bold', color=title_color)

    all_vals = q1 + q3
    y_min, y_max = min(all_vals), max(all_vals)
    y_range = y_max - y_min if y_max != y_min else 1.0

    ax.set_ylim(y_min - y_range * 0.4, y_max + y_range * 0.6)

    # 4. Wilcoxon + Bonferroni
    if p_friedman < 0.05:
        try:
            raw_p1 = stats.wilcoxon(df_sub['Pre'], df_sub['Post']).pvalue
            raw_p2 = stats.wilcoxon(df_sub['Post'], df_sub['Delay']).pvalue
            raw_p3 = stats.wilcoxon(df_sub['Pre'], df_sub['Delay']).pvalue

            n_comp = 3
            p_pre_post   = min(raw_p1 * n_comp, 1.0)
            p_post_delay = min(raw_p2 * n_comp, 1.0)
            p_pre_delay  = min(raw_p3 * n_comp, 1.0)
        except ValueError:
            p_pre_post, p_post_delay, p_pre_delay = 1.0, 1.0, 1.0

        top_y_base = y_max + y_range * 0.15

        def draw_bracket(ax, x1, x2, y, p_val, align='top'):
            h = y_range * 0.05
            text = format_p_value(p_val)
            text_color = 'red' if p_val < 0.05 else 'black'

            if align == 'top':
                ax.plot([x1, x1, x2, x2], [y, y+h, y+h, y], lw=1.5, c='black')
                ax.text((x1+x2)*0.5, y+h*1.5, text, ha='center', va='bottom', color=text_color, fontsize=9, fontweight='bold')
            else:
                ax.plot([x1, x1, x2, x2], [y, y-h, y-h, y], lw=1.5, c='black')
                ax.text((x1+x2)*0.5, y-h*2.5, text, ha='center', va='top', color=text_color, fontsize=9, fontweight='bold')

        draw_bracket(ax, 0, 1, top_y_base, p_pre_post, align='top')
        draw_bracket(ax, 1, 2, top_y_base, p_post_delay, align='top')

        bottom_y = y_min - y_range * 0.15
        draw_bracket(ax, 0, 2, bottom_y, p_pre_delay, align='bottom')
    else:
        ax.text(0.5, 0.5, "No Sig. Diff", transform=ax.transAxes, ha='center', alpha=0.3)

def analyze_time_series():
    print_separator("PART 2: Time Series Analysis (Friedman -> Wilcoxon[Bonferroni])")

    try:
        data_containers = {'Translation': {}, 'Sentence': {}}

        for sheet in SHEETS:
            df_pre = pd.read_excel(FILE_PRE, sheet_name=sheet, header=0, dtype=str)
            df_post = pd.read_excel(FILE_POST, sheet_name=sheet, header=0, dtype=str)
            df_delay = pd.read_excel(FILE_DELAY, sheet_name=sheet, header=0, dtype=str)

            t_df = pd.DataFrame({
                'Pre': df_pre.iloc[:, 2].apply(clean_score),
                'Post': df_post.iloc[:, 2].apply(clean_score),
                'Delay': df_delay.iloc[:, 2].apply(clean_score)
            }).dropna()

            s_df = pd.DataFrame({
                'Pre': df_pre.iloc[:, 40].apply(clean_score),
                'Post': df_post.iloc[:, 55].apply(clean_score),
                'Delay': df_delay.iloc[:, 40].apply(clean_score)
            }).dropna()

            if len(t_df) > 0: data_containers['Translation'][sheet] = t_df
            if len(s_df) > 0: data_containers['Sentence'][sheet] = s_df

        for subject, groups_data in data_containers.items():
            if not groups_data: continue
            n_groups = len(groups_data)
            fig, axes = plt.subplots(1, n_groups, figsize=(5 * n_groups, 7))
            if n_groups == 1: axes = [axes]

            print(f"\nplotting {subject}...")
            for idx, (group_name, df_data) in enumerate(groups_data.items()):
                plot_time_series_with_friedman(axes[idx], df_data, group_name, subject)

            plt.subplots_adjust(bottom=0.25)
            plt.show()

    except Exception as e:
        print(f"❌ Time Series Error: {e}")

# ==========================================
# 🧠 PART 3: NASA-TLX
# ==========================================
def analyze_nasa_tlx():
    print_separator("PART 3: NASA-TLX Analysis (All 6 Dimensions)")

    dimensions = [
        {'name': 'Mental Demand', 'col': 28},
        {'name': 'Physical Demand', 'col': 29},
        {'name': 'Temporal Demand', 'col': 30},
        {'name': 'Performance', 'col': 31},
        {'name': 'Effort', 'col': 32},
        {'name': 'Frustration', 'col': 33}
    ]

    for dim in dimensions:
        all_data = []
        for sheet in SHEETS:
            try:
                df = pd.read_excel(FILE_POST, sheet_name=sheet, header=0, dtype=str)
                vals = df.iloc[:, dim['col']].apply(clean_score).dropna()
                for v in vals: all_data.append({'Group': sheet, 'Score': v})
            except: pass

        df_plot = pd.DataFrame(all_data)
        if not df_plot.empty:
            print(f"\n🔹 Dimension: {dim['name']}")
            fig, axes = plt.subplots(1, 2, figsize=(16, 7))
            perform_kruskal_dunn_plot(df_plot, 'Score', 'Group', dim['name'], "Score", axes[0], axes[1])
            plt.subplots_adjust(bottom=0.25)
            plt.show()

# ==========================================
# ⚡ PART 4: Paas Efficiency (合併表格 + Kruskal 分析)
# ==========================================
def analyze_paas_efficiency():
    print_separator("PART 4: Paas Efficiency Analysis")

    all_data = []
    for sheet in SHEETS:
        try:
            df = pd.read_excel(FILE_POST, sheet_name=sheet, header=0, usecols=[2, 55, 28], dtype=str)
            df.columns = ['Trans', 'Sent', 'Mental']
            for c in df.columns: df[c] = df[c].apply(clean_score)
            df['Group'] = sheet
            all_data.append(df.dropna())
        except: pass

    if not all_data: return
    big_df = pd.concat(all_data)

    # 1. 計算 Z-Score
    for col in ['Trans', 'Sent', 'Mental']:
        big_df[f'Z_{col}'] = (big_df[col] - big_df[col].mean()) / big_df[col].std()

    # 2. 計算 Efficiency (E) 值
    big_df['E_Trans'] = (big_df['Z_Trans'] - big_df['Z_Mental']) / math.sqrt(2)
    big_df['E_Sent']  = (big_df['Z_Sent']  - big_df['Z_Mental']) / math.sqrt(2)

    for subj in ['Trans', 'Sent']:
        # --- A. 畫散佈圖 (Quadrant Analysis) ---
        fig, ax = plt.subplots(figsize=(8, 8))
        lims = [-2.5, 2.5]
        ax.plot(lims, lims, color='gray', linestyle='--', linewidth=1.5, label='Efficiency = 0')

        centroids = big_df.groupby('Group')[[f'Z_{subj}', 'Z_Mental']].mean().reset_index()
        sns.scatterplot(data=big_df, x='Z_Mental', y=f'Z_{subj}', hue='Group', style='Group', alpha=0.4, s=60, ax=ax)
        sns.scatterplot(data=centroids, x='Z_Mental', y=f'Z_{subj}', hue='Group', style='Group', s=250, edgecolor='black', zorder=10, ax=ax, legend=False)

        ax.set_xlim(lims); ax.set_ylim(lims)
        ax.axhline(0, color='k', linewidth=0.5); ax.axvline(0, color='k', linewidth=0.5)
        ax.set_xlabel("Mental Effort Z-score (R)", fontweight='bold')
        ax.set_ylabel("Performance Z-score (P)", fontweight='bold')
        ax.set_title(f"Efficiency Quadrant: {subj}")
        ax.text(lims[0]+0.5, lims[1]-0.5, "High Efficiency", fontsize=12, color='green', ha='left', va='top', fontweight='bold', alpha=0.6)
        ax.text(lims[1]-0.5, lims[0]+0.5, "Low Efficiency", fontsize=12, color='red', ha='right', va='bottom', fontweight='bold', alpha=0.6)
        plt.tight_layout()
        plt.show()

        # --- B. 文字輸出：合併的詳細統計表格 (含 E 的 Std/Med) ---
        stats_data = []
        for g in SHEETS:
            sub = big_df[big_df['Group'] == g]
            if len(sub) == 0: continue
            stats_data.append({
                'Group': g,
                'N': int(len(sub)),
                'Mental(Mean)': sub['Z_Mental'].mean(),
                'Perf(Mean)': sub[f'Z_{subj}'].mean(),
                'E(Mean)': sub[f'E_{subj}'].mean(),
                'E(Std)': sub[f'E_{subj}'].std(),     # 新增：E 的標準差
                'E(Med)': sub[f'E_{subj}'].median()   # 新增：E 的中位數
            })

        print(f"\n📊 Combined Detailed Stats for {subj} (Mental, Perf, Efficiency):")
        if stats_data:
            df_eff_stats = pd.DataFrame(stats_data).set_index('Group')
            # 使用 to_string 格式化輸出
            print(df_eff_stats.round(3).to_string())
        print("-" * 60)

        # --- C. E 值的 Kruskal-Wallis 分析 ---
        # 呼叫繪圖函式，但設定 print_stats=False 以免重複印出基本統計表
        print(f"\n🔹 Analyzing Efficiency (E-Value) Differences: {subj}")
        fig, axes = plt.subplots(1, 2, figsize=(16, 7))

        perform_kruskal_dunn_plot(
            big_df,
            f'E_{subj}',
            'Group',
            f"Efficiency (E) Analysis - {subj}",
            "Efficiency Score (E)",
            axes[0], axes[1],
            print_stats=False # 關閉內建的表格輸出
        )
        axes[0].axhline(0, ls='--', c='gray')
        plt.subplots_adjust(bottom=0.25)
        plt.show()

# ==========================================
# ➖ PART 5: Difference Analysis
# ==========================================
def analyze_differences():
    print_separator("PART 5: Score Difference Analysis")

    all_data = []
    for sheet in SHEETS:
        try:
            df_pre = pd.read_excel(FILE_PRE, sheet_name=sheet, header=0, dtype=str)
            pre_t = df_pre.iloc[:, 2].apply(clean_score)
            pre_s = df_pre.iloc[:, 40].apply(clean_score)

            df_post = pd.read_excel(FILE_POST, sheet_name=sheet, header=0, dtype=str)
            post_t = df_post.iloc[:, 2].apply(clean_score)
            post_s = df_post.iloc[:, 55].apply(clean_score)

            df_delay = pd.read_excel(FILE_DELAY, sheet_name=sheet, header=0, dtype=str)
            delay_t = df_delay.iloc[:, 2].apply(clean_score)
            delay_s = df_delay.iloc[:, 40].apply(clean_score)

            n = min(len(pre_t), len(post_t), len(delay_t))
            temp_df = pd.DataFrame({
                'Group': [sheet]*n,
                'Diff_Post_Pre_Trans': post_t[:n].values - pre_t[:n].values,
                'Diff_Delay_Pre_Trans': delay_t[:n].values - pre_t[:n].values,
                'Diff_Delay_Post_Trans': delay_t[:n].values - post_t[:n].values,
                'Diff_Post_Pre_Sent': post_s[:n].values - pre_s[:n].values,
                'Diff_Delay_Pre_Sent': delay_s[:n].values - pre_s[:n].values,
                'Diff_Delay_Post_Sent': delay_s[:n].values - post_s[:n].values,
            }).dropna()
            all_data.append(temp_df)
        except Exception as e:
            print(f"❌ Error for sheet '{sheet}': {e}")

    if not all_data: return
    big_df = pd.concat(all_data)

    metrics = [
        'Diff_Post_Pre_Trans', 'Diff_Delay_Pre_Trans', 'Diff_Delay_Post_Trans',
        'Diff_Post_Pre_Sent', 'Diff_Delay_Pre_Sent', 'Diff_Delay_Post_Sent'
    ]
    for metric in metrics:
        clean_title = metric.replace('Diff_', '').replace('_', ' ')
        print(f"\n🔹 Analyzing: {clean_title}")
        fig, axes = plt.subplots(1, 2, figsize=(16, 7))
        perform_kruskal_dunn_plot(big_df, metric, 'Group', clean_title, "Score Difference", axes[0], axes[1])
        axes[0].axhline(0, ls='--', c='gray')
        plt.subplots_adjust(bottom=0.25)
        plt.show()

# ==========================================
# 🚀 執行
# ==========================================
if __name__ == "__main__":
    analyze_basic_scores()
    analyze_time_series()
    analyze_nasa_tlx()
    analyze_paas_efficiency()
    analyze_differences()