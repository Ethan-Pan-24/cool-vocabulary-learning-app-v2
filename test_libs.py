
try:
    import pandas as pd
    print("pandas imported")
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    print("matplotlib imported")
    import seaborn as sns
    print("seaborn imported")
    import scipy.stats
    print("scipy imported")
    try:
        import scikit_posthocs as sp
        print("scikit_posthocs imported")
    except ImportError:
        print("scikit_posthocs NOT found")
        
    # Test Plot
    data = {'group': ['A', 'A', 'B', 'B'], 'val': [1, 2, 3, 4]}
    df = pd.DataFrame(data)
    
    fig, ax = plt.subplots()
    sns.boxplot(x='group', y='val', data=df, ax=ax)
    print("Plot created successfully")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
