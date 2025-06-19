import streamlit as st , pandas as pd , numpy as np , plotly.express as px
import plotly.graph_objects as go
from mftool import Mftool
from datetime import date
import mstarpy
from mstarpy import search_funds
from dateutil.relativedelta import relativedelta

mf = Mftool()

st.title("Mutual Fund Analysis")

option = st.sidebar.selectbox(
    "Choose the action",
    ["View Available Funds","Historical NAVs","Compare Fund NAV","Compare Funds Return","Risk and Volatility Analysis","Fund Recommendations","Fund Selector","Fund Investment"]
)

fund_names = {v:k for k,v in mf.get_scheme_codes().items()}
final_result = pd.DataFrame()

def fetch_mutual_fund_data(mutual_fund_code):
    print(f"Fetching NAV history for scheme code: {mutual_fund_code}")
    df = (mf.get_scheme_historical_nav(mutual_fund_code, as_Dataframe=True).reset_index() \
          .assign(nav=lambda x: x['nav'].astype(float),
                  date=lambda x: pd.to_datetime(x['date'], format='%d-%m-%Y')) \
          .sort_values('date') \
          .reset_index(drop=True) \
          )
    Fund_name = mf.get_scheme_details(mutual_fund_code)['scheme_name']
    df['Fund Name'] = Fund_name

    return df

if option == "View Available Funds":
    st.header("Available Funds")
    Fund_house = st.sidebar.text_input("Enter the Fund's House")
    Fund = mf.get_available_schemes(Fund_house)
    st.write(pd.DataFrame(Fund.items(),columns=["Scheme Code","Scheme Name"]) if Fund else "Sorry! No such fund found")

if option == "Historical NAVs":
    st.header("Historical NAVs")
    Fund_code = fund_names[st.sidebar.selectbox("Select a scheme",fund_names.keys())]
    Fund_nav = (mf.get_scheme_historical_nav(Fund_code,as_Dataframe=True).reset_index()\
          .assign(nav=lambda x: x['nav'].astype(float),
                 date=lambda x: pd.to_datetime(x['date'], format='%d-%m-%Y'))\
          .sort_values('date',ascending=False)\
          .reset_index(drop=True)\
         )
    Fund_name = mf.get_scheme_details(Fund_code)['scheme_name']
    fig = px.line(Fund_nav, x="date", y="nav", title="Fund historical NAVs")
    st.plotly_chart(fig)
    st.write(Fund_nav)

if option == "Compare Fund NAV":
    st.header("Compare NAVs")
    selected_funds = st.sidebar.multiselect("Select funds to compare",options=list(fund_names.keys()))

    if selected_funds:
        compare_df = pd.DataFrame()
        for fund in selected_funds:
            code = fund_names[fund]
            data = mf.get_scheme_historical_nav(code,as_Dataframe=True)
            data = data.reset_index().rename(columns={'index':'date'})
            data['date'] = pd.to_datetime(data['date'], format='%d-%m-%Y',dayfirst=True).sort_values()
            data['nav'] = data['nav'].astype(float)
            data['name'] = mf.get_scheme_details(code)['scheme_name']
            compare_df[fund] = data.set_index('date')['nav']
            if len(selected_funds) > 1:
                fig_compare = px.line(compare_df, title= "Comparison of funds")
                fig_compare.update_layout(
                    legend=dict(
                        orientation="v",
                        yanchor="bottom",
                        y=0.8,
                        xanchor="left",
                        x=0
                    )
                )
                fig_compare.update_layout(
                    title=dict(
                        text=f"Cumulative Returns ",
                        x=0.5,  # Center horizontally
                        xanchor='center'
                    )
                )
                st.plotly_chart(fig_compare)

if option == "Compare Funds Return":
    st.header("Compare Funds Return")
    selected_funds = st.sidebar.multiselect("Select funds to compare", options=list(fund_names.keys()))
    num_years = st.sidebar.slider("Select return period (years)", min_value=1, max_value=10, value=1)

    if selected_funds:
        all_funds = pd.DataFrame()
        for fund in selected_funds:
            code = fund_names[fund]
            data = fetch_mutual_fund_data(code)
            all_funds = pd.concat([all_funds,data])

        st.session_state['all_funds'] = all_funds

    starting_date = date.today()
    ending_date = starting_date - relativedelta(years=num_years)
    start_date = pd.to_datetime(starting_date, format='%d-%m-%Y')
    end_date = pd.to_datetime(ending_date, format='%d-%m-%Y')

    df = all_funds.sort_values(['Fund Name', 'date'])
    fund_selected_time = df[(df['date'] > end_date) & (df['date'] < start_date)]
    fund_selected_time['daily_return_%'] = fund_selected_time.groupby('Fund Name')['nav'].pct_change() * 100
    fund_selected_time['cumulative_return_%'] = fund_selected_time.groupby('Fund Name')['nav'].transform(lambda x: (x / x.iloc[0] - 1) * 100)




    tab1, tab2, tab3 = st.tabs(["Cumulative Returns", "Absolute Return %", "CAGR %"])

    #Plotting the Graph
    with tab1:

        fig_total_returns = px.line(
        fund_selected_time,
        x='date',
        y='cumulative_return_%',
        color='Fund Name',
        title=f'Cumulative Returns - Last {num_years} Year{"s" if num_years > 1 else ""}',
        labels={'growth': 'Returns', 'date': 'Date', 'Fund Name': 'Fund'},
        width = 1800,
        height = 600
        )
        fig_total_returns.update_layout(
        legend=dict(
            title='Fund Name',
            orientation='v',  # 'v' for vertical list, 'h' for horizontal
            yanchor='top',
            y=1,
            xanchor='left',
            x=0
            )
        )
    st.plotly_chart(fig_total_returns, use_container_width=False)

    with tab2:
        # Absolute Return = (End NAV - Start NAV) / Start NAV * 100
        summary = fund_selected_time.groupby('Fund Name').agg(start_nav=('nav', 'first'), end_nav=('nav', 'last'))
        summary['Absolute Return (%)'] = ((summary['end_nav'] - summary['start_nav']) / summary['start_nav']) * 100
        st.subheader(f"Absolute Return % over {num_years} year(s)")
        st.dataframe(summary[['Absolute Return (%)']    ].round(2))

    with tab3:
        # CAGR = (End NAV / Start NAV) ^ (1 / years) - 1
        summary['CAGR (%)'] = ((summary['end_nav'] / summary['start_nav']) ** (1 / num_years) - 1) * 100
        st.subheader(f"CAGR % over {num_years} year(s)")
        st.dataframe(summary[['CAGR (%)']].round(2))

if option == "Risk and Volatility Analysis":
    st.header("Risk and Volatility Analysis")
    selected_fund_name = st.sidebar.selectbox("Select a scheme", list(fund_names.keys()))
    fund_code = fund_names[selected_fund_name]

    rolling_window_days = st.sidebar.slider("Rolling Window (days)", min_value=5, max_value=120, value=30)

    # Define end date as today, start date as X days back
    end_date = date.today()
    start_date = end_date - relativedelta(days=rolling_window_days * 5)  # enough data for rolling window

    # Fetch NAV data
    nav_data = (
        mf.get_scheme_historical_nav(fund_code, as_Dataframe=True)
        .reset_index()
        .assign(nav=lambda x: x['nav'].astype(float),
                date=lambda x: pd.to_datetime(x['date'], format='%d-%m-%Y'))
        .sort_values('date')
    )

    # Filter to selected range
    nav_data = nav_data[
        (nav_data['date'] >= pd.to_datetime(start_date)) & (nav_data['date'] <= pd.to_datetime(end_date))]
    nav_data['Fund Name'] = selected_fund_name

    # Calculate daily return
    nav_data['daily_return'] = nav_data['nav'].pct_change()

    # Calculate rolling volatility
    nav_data['rolling_volatility'] = (
            nav_data['daily_return']
            .rolling(window=rolling_window_days)
            .std() * np.sqrt(252)*100
    )

    # Drop NaNs for clean chart
    nav_data = nav_data.dropna(subset=['rolling_volatility'])

    # Plot
    fig = px.line(
        nav_data,
        x='date',
        y='rolling_volatility',
        title=f"Rolling Volatility % - {selected_fund_name}",
        labels={'rolling_volatility': 'Annualized Volatility (%)'},
    )

    fig.update_layout(title_x=0.5)

    # Show plot
    st.plotly_chart(fig, use_container_width=True)

if option == "Fund Recommendations":
    st.header("Top Performing Funds")
    selected_funds = st.sidebar.multiselect("Select funds to evaluate", list(fund_names.keys()))
    num_years = st.sidebar.slider("Select period (years)", 1, 10, 3)

    if selected_funds:
        all_funds = pd.DataFrame()
        for fund in selected_funds:
            code = fund_names[fund]
            data = fetch_mutual_fund_data(code)
            all_funds = pd.concat([all_funds, data])

        # Date filtering
        ending_date = date.today()
        starting_date = ending_date - relativedelta(years=num_years)
        all_funds = all_funds[(all_funds['date'] >= pd.to_datetime(starting_date)) & (all_funds['date'] <= pd.to_datetime(ending_date))]

        all_funds['daily_return'] = all_funds.groupby('Fund Name')['nav'].pct_change()

        summary = all_funds.groupby('Fund Name').agg(
            start_nav=('nav', 'first'),
            end_nav=('nav', 'last'),
            start_date=('date', 'first'),
            end_date=('date', 'last'),
            cumulative_return_pct=('nav', lambda x: (x.iloc[-1] / x.iloc[0] - 1) * 100),
            volatility_pct=('daily_return', lambda x: x.std() * np.sqrt(252) * 100),

        )

        #Calculating Annulised Return
        summary['years'] = (summary['end_date'] - summary['start_date']).dt.days / 365.25
        summary['Annualised'] = ((summary['end_nav'] / summary['start_nav']) ** (1 / summary['years']) - 1) * 100

        # Calculating Sharpe Ratio
        volatility = all_funds.groupby('Fund Name')['daily_return'].std() * (252 ** 0.5)  # Annualized
        risk_free_rate = 0.04
        avg_return = all_funds.groupby('Fund Name')['daily_return'].mean() * 252
        sharpe_ratio = (avg_return - risk_free_rate) / volatility

        st.subheader("Recommended Funds (based on CAGR, Cumulative Return, and Volatility)")
        Risk_df = pd.DataFrame({
            "Volatility (%)": volatility * 100,
            "Sharpe Ratio": sharpe_ratio,
            "CAGR %": summary['cumulative_return_pct'],
            "Annualised Return %": summary['Annualised']

        }).round(2)
        st.dataframe(Risk_df)

if option == "Fund Selector":
    Fund_house = st.sidebar.text_input("Enter the keyword to find funds")
    num_years = st.sidebar.slider("Select period (years)", 1, 10, 3)
    st.header(f"Available Funds for keyword {Fund_house} ")
    Fund = mf.get_available_schemes(Fund_house)
    all_funds = pd.DataFrame(Fund.items(), columns=["Scheme Code", "Scheme Name"])
    st.write(all_funds)

    # Market data for benchmark
    benchmark_df = fetch_mutual_fund_data("147666")
    # Date filtering
    ending_date = date.today()
    starting_date = ending_date - relativedelta(years=num_years)
    benchmark_df = benchmark_df[
        (benchmark_df['date'] >= pd.to_datetime(starting_date)) & (benchmark_df['date'] <= pd.to_datetime(ending_date))]
    benchmark_df['benchmark_return'] = benchmark_df.groupby('Fund Name')['nav'].pct_change()

    window_size = 252 * num_years



    blank_df = pd.DataFrame()
    for i in range(len(all_funds)):
        df = fetch_mutual_fund_data(all_funds['Scheme Code'][i])
        blank_df = pd.concat([blank_df,df])


        # Date filtering
        ending_date = date.today()
        starting_date = ending_date - relativedelta(years=num_years)
        blank_df = blank_df[(blank_df['date'] >= pd.to_datetime(starting_date)) & (blank_df['date'] <= pd.to_datetime(ending_date))]

        blank_df['daily_return'] = blank_df.groupby('Fund Name')['nav'].pct_change()

        summary = blank_df.groupby('Fund Name').agg(
            start_nav=('nav', 'first'),
            end_nav=('nav', 'last'),
            start_date=('date', 'first'),
            end_date=('date', 'last'),
            cumulative_return_pct=('nav', lambda x: (x.iloc[-1] / x.iloc[0] - 1) * 100),
            volatility_pct=('daily_return', lambda x: x.std() * np.sqrt(252) * 100),

        )

        # Calculating Annulised Return
        summary['years'] = (summary['end_date'] - summary['start_date']).dt.days / 365.25
        summary['Annualised'] = ((summary['end_nav'] / summary['start_nav']) ** (1 / summary['years']) - 1) * 100


        # Calculating Sharpe Ratio
        volatility = blank_df.groupby('Fund Name')['daily_return'].std() * (252 ** 0.5)  # Annualized
        risk_free_rate = 0.06
        avg_return = blank_df.groupby('Fund Name')['daily_return'].mean() * 252
        sharpe_ratio = (avg_return - risk_free_rate) / volatility



        Risk_df = pd.DataFrame({
        "Volatility (%)": volatility * 100,
        "Sharpe Ratio": sharpe_ratio,
        "CAGR %": summary['cumulative_return_pct'],
        f"Annualised Return %": summary['Annualised'],

        }).round(2)

    final_result=pd.concat([final_result,Risk_df])
    st.subheader(f"Available Fund's with details {Fund_house} ")

    #Below is code for calculating Upside and downward capture ratio

    # Date filtering
    ending_date = date.today()
    starting_date = ending_date - relativedelta(years=num_years)
    blank_df = blank_df[
        (blank_df['date'] >= pd.to_datetime(starting_date)) & (blank_df['date'] <= pd.to_datetime(ending_date))]


    merged_df = pd.merge(blank_df, benchmark_df[['date', 'benchmark_return','Fund Name']], on='date', how='inner')

    result_df = pd.DataFrame()
    funds = merged_df['Fund Name_x'].unique()
    capture_data = []

    for fund in funds:
        fund_data = merged_df[merged_df['Fund Name_x'] == fund]

        # Ensure no division by zero
        up_data = fund_data[fund_data['benchmark_return'] > 0]
        down_data = fund_data[fund_data['benchmark_return'] < 0]

        if not up_data.empty and not down_data.empty:
            up_capture = up_data['daily_return'].mean() / up_data['benchmark_return'].mean()
            down_capture = down_data['daily_return'].mean() / down_data['benchmark_return'].mean()

            capture_data.append({
                "Fund Name": fund,
                "Up Capture": round(up_capture, 2)*100,
                "Down Capture": round(down_capture, 2)*100
            })
    # Create DataFrame from list of dicts
    result_df = pd.DataFrame(capture_data)
    Combined_result_df = pd.DataFrame()
    Combined_result_df = pd.merge(final_result, result_df, on='Fund Name', how='inner')
    st.write(Combined_result_df)


    #User Filtering options

    Sharpe_ratio_selection = st.sidebar.slider("Select the minimum Sharpe ratio", min_value=0.1, max_value=10.0, value=0.1,step=0.02)
    Minimum_Annualised_return = st.sidebar.number_input("Write Minimum Absolute Return you want", min_value = 0.0, max_value = 1000.0,value=6.0)
    Minimum_upside_capture = st.sidebar.number_input("Write Minimum Upside Capture Ratio you want", min_value=0.0, max_value=500.0, value=30.0)
    Maximum_downside_capture = st.sidebar.number_input("Write Maximum Downside Capture Ratio you can endure", min_value=10.0, max_value=200.0, value=100.0)


    # Display in Streamlit
    selection = Combined_result_df[(Combined_result_df['Sharpe Ratio'] >= Sharpe_ratio_selection) & (Combined_result_df['Annualised Return %'] >= Minimum_Annualised_return) & (Combined_result_df['Up Capture'] >= Minimum_upside_capture) & (Combined_result_df['Down Capture'] <= Maximum_downside_capture)]
    st.subheader(f"Available Funds for {Fund_house} after filtering")
    st.write(selection)

keywords = ["Aditya", "HDFC", "SBI", "ICICI", "Kotak", "Nippon", "Axis", "Franklin", "Tata", "UTI","Parag Parikh","Quant"]
all_results = []
Scheme_with_code = pd.DataFrame()

for kw in keywords:
    try:
        response = search_funds(term=kw, field=["Name", "fundShareClassId"], country="in", pageSize=500)
        if response:
            all_results.extend(response)
    except Exception as e:
        print(f"Error searching for {kw}: {e}")

Scheme_with_code = pd.DataFrame(all_results).drop_duplicates(subset="fundShareClassId")

scheme_code = Scheme_with_code.set_index('Name')['fundShareClassId'].to_dict()

if option == "Fund Investment" :
    st.header("Fund Investment")

    Fund_code = scheme_code[st.sidebar.selectbox("Select a scheme",scheme_code.keys())]
    response = mstarpy.search_funds(term=Fund_code, field=["Name", "fundShareClassId"], country="in",pageSize=40)
    df = pd.DataFrame(response)

    fund_code = df['fundShareClassId']
    fund_details = mstarpy.Funds(term= fund_code,country="in")
    fund_eq_holdings = pd.DataFrame()

    sector_allocation = pd.DataFrame(fund_details.holdings(holdingType="all"))
    fund_eq_holdings = sector_allocation
    fund_eq_holdings['Fund Name'] = fund_details.name
    fund_eq_holdings = fund_eq_holdings[["securityName","weighting","numberOfShare","sector","holdingType","assessment","totalReturn1Year","susEsgRiskScore"]]

    st.write(fund_eq_holdings)

    # Group by sector and sum weighting
    sector_weights = fund_eq_holdings.groupby("sector")["weighting"].sum().reset_index()

    # Plot horizontal bar chart
    fig = px.bar(
        sector_weights,
        x="weighting",
        y="sector",
        color="sector",
        orientation="h",
        title="Sector-wise Weighting",
        labels={"weighting": "Total Weighting", "sector": "Sector"},
        text="weighting"
    )

    fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    fig.update_layout(yaxis=dict(categoryorder='total ascending'))
    fig.update_layout(
        yaxis=dict(categoryorder='total ascending'),
        legend=dict(font=dict(size=10))  # Smaller legend text
    )

    # Show in Streamlit
    st.plotly_chart(fig,use_container_width=True)

    # Group by Holding Type and sum weighting
    type_weights = fund_eq_holdings.groupby("holdingType")["weighting"].sum().reset_index()

    # Plot pie chart
    fig_type = go.Figure(data=[go.Pie(
        labels = type_weights["holdingType"],
        values = type_weights["weighting"],
        hole=0.4,
        pull=[0, 0, 0.2],
        textinfo='percent+label',
        insidetextorientation='radial',
        marker=dict(line=dict(color='black', width=2))
    )])

    fig_type.update_layout(
        title_text="Holding Type Split",
        legend=dict(font=dict(size=10), orientation="h", y=-0.2)
    )

    st.plotly_chart(fig_type, use_container_width=True)

    # Group by assessment and count stocks
    assessment_count = fund_eq_holdings.groupby("assessment")["securityName"].count().reset_index()

    # Plot pie chart
    fig_type = go.Figure(data=[go.Pie(
        labels=assessment_count["assessment"],
        values=assessment_count["securityName"],
        hole=0.4,

        textinfo='percent+label',
        insidetextorientation='radial',
        marker=dict(line=dict(color='black', width=2))
    )])

    fig_type.update_layout(
        title_text="Holding Type Split",
        legend=dict(font=dict(size=10), orientation="h", y=-0.2)
    )

    st.plotly_chart(fig_type, use_container_width=True)








