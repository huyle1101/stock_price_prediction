from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import seaborn as sns
import os
import numpy as np

def calc_metrics(df, actual_col="Adj_Close", pred_col="Arima_Predicted_Close", ticker_col="Ticker"):
    df = df.copy()
    
    if ticker_col and ticker_col in df.columns and df[ticker_col].nunique() > 1:
        return df.groupby(ticker_col).apply(
            lambda x: calc_metrics(x, actual_col, pred_col, ticker_col=None)
        ).reset_index()
        
    df["Prev_Actual"] = df[actual_col].shift(1)
    df["Prev_Pred"] = df[pred_col].shift(1)
    df = df.dropna(subset=[actual_col, pred_col, "Prev_Actual", "Prev_Pred"])
    
    y_true = df[actual_col]
    y_pred = df[pred_col]
    
    mse = mean_squared_error(y_true, y_pred)
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    mape = np.mean(np.abs((y_true - y_pred) / y_true))
    r2 = r2_score(y_true, y_pred)
    
    actual_dir = np.sign(y_true.values - df["Prev_Actual"].values)
    pred_dir = np.sign(y_pred.values - df["Prev_Pred"].values)
    da = np.mean(actual_dir == pred_dir)
    
    mask = actual_dir != 0
    tpa = np.mean(actual_dir[mask] == pred_dir[mask]) if np.any(mask) else np.nan
    
    actual_vol = y_true - y_true.mean()
    pred_vol = y_pred - y_pred.mean()
    v_rmse = np.sqrt(mean_squared_error(actual_vol, pred_vol))
    
    metrics = pd.Series({
        "MSE": mse, "MAE": mae, "MAPE": mape, 
        "RMSE": rmse, "R2": r2, "DA": da, 
        "TPA": tpa, "V-RMSE": v_rmse
    })
    
    if ticker_col is None:
        return metrics
    else:
        res_df = pd.DataFrame([metrics])
        if "Ticker" in df.columns:
            res_df.insert(0, "Ticker", df["Ticker"].iloc[0])
        return res_df

def plot_prediction_results(df, save_dir=None, model=None):
    ticker = df['Ticker'].iloc[0] if 'Ticker' in df.columns else 'Unknown'
    
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    sns.set(style="whitegrid")
    plt.figure(figsize=(12, 6))
    
    plt.plot(df['Actual_Close'], label='Actual Close', color='#1f77b4', linewidth=2)
    plt.plot(df[f'{model}_Predicted_Close'], label=f'{model} Predicted', color='#d62728', linestyle='--', linewidth=1.5)
    
    plt.title(f"{model} predicted results: {ticker}", fontsize=15)
    plt.xlabel("Days (Test Period)", fontsize=12)
    plt.ylabel("Price", fontsize=12)
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    
    save_path = os.path.join(save_dir, f"{model}_{ticker}.png")
    plt.savefig(save_path, bbox_inches='tight', dpi=150)
    plt.show()
    plt.close()