
"""
Created on Thu Nov 19 20:04:35 2020
@author: Rasmus
"""

import pandas as pd
import pulp

###################### OPTIONS
teams_create=30

max_budget=50000
min_budget=45000

qb_stacking=2
opp_stack=1
def_rb_stack='on'
avoid_opp_def='on'
#####################



##### DATA PREPARATION
df = pd.read_excel (r'nfl.xlsx') 
player_number=9
df['own_max']=round(teams_create*df['own_max']/100,0)
df = df.loc[(df["fpts"] >= 1)] 
df['total']=1
df['low_owned']=0
df.loc[(df['proj_own'] <= 5) & (df['pos'] =='WR'), 'low_owned'] =1
df.loc[df['pos'].str.contains("WR"), "WR"] = 1
df.loc[df['pos'].str.contains("TE"), "TE"] = 1
df.loc[df['pos'].str.contains("RB"), "RB"] = 1
df.loc[df['pos'].str.contains("QB"), "QB"] = 1
df.loc[df['pos'].str.contains("DST"), "DEF"] = 1
df=df.fillna(0)
df_copy=df.copy()
df_copy['used']=0
df_copy['player_id']=df_copy['player_id'].astype(str)
opt_points=1000


def optimize(df, maxpoints):
       
    ### SOLVER VARIABLES
    player_items = list(df['name'])
    player_ids = df.index   
    teams = df['team']
    unique_teams = df['team'].unique()   
    player_in_team = teams.str.get_dummies()
    costs = dict(zip(player_ids,df['price']))
    points = dict(zip(player_ids,df['fpts']))
    wides = dict(zip(player_ids,df['WR']))
    rbs= dict(zip(player_ids,df['RB']))
    tes = dict(zip(player_ids,df['TE']))
    qbs = dict(zip(player_ids,df['QB']))
    defs = dict(zip(player_ids,df['DEF']))
    low_owns=dict(zip(player_ids,df['low_owned']))    
    total_team = dict(zip(unique_teams,df['total']))
    
    player_vars_id = pulp.LpVariable.dicts('player', player_ids, cat='Binary')
    team_vars = pulp.LpVariable.dicts('team', unique_teams, cat='Binary')
    
    #### PROBLEM TO SOLVE
    prob = pulp.LpProblem("LuOptimize",pulp.LpMaximize)
    prob += pulp.lpSum([points[p] * player_vars_id[p] for p in player_ids])
      
    ### CONSTRAINTS
    
    # number of teams used 
    for team in unique_teams:
      prob += pulp.lpSum(
          [player_in_team[team][i] * player_vars_id[i] for i in player_ids]
      ) >= team_vars[team]
      prob += pulp.lpSum(
          [player_in_team[team][i] * player_vars_id[i] for i in player_ids]
      ) <= 4        
    prob += pulp.lpSum([total_team[t] * team_vars[t] for t in unique_teams]) >= 3
    
    ### Quarterback + 1-3 receiver
    for gkid in player_ids:
       if df['pos'][gkid] == 'QB':
           prob += pulp.lpSum([player_vars_id[i] for i in player_ids if 
                                 (df['team'][i] == df['team'][gkid] and 
                                  df['pos'][i] in ('WR', 'TE'))] + 
                                  [-(qb_stacking)*player_vars_id[gkid]]) >= 0
    
    ### running back + 1 def
    if def_rb_stack=='on':
        for gkid in player_ids:
            if df['pos'][gkid] == 'DST':
                prob += pulp.lpSum([player_vars_id[i] for i in player_ids if 
                                  (df['team'][i] == df['team'][gkid] and 
                                    df['pos'][i] in ('RB'))] + 
                                    [-1*player_vars_id[gkid]]) >= 0                          
                        
    ### Don't stack with opposing DST:
    if avoid_opp_def==1:
        for dstid in player_ids:
            if df['pos'][dstid] == 'DST':
                prob += pulp.lpSum([player_vars_id[i] for i in player_ids if
                                    df['team'][i] == df['opp'][dstid]] +
                                    [8*player_vars_id[dstid]]) <= 8
                                
    ### Stack QB with 1 opposing player:
    for qbid in player_ids:
        if df['pos'][qbid] == 'QB':
            prob += pulp.lpSum([player_vars_id[i] for i in player_ids if
                                (df['team'][i] == df['opp'][qbid] and 
                                 df['pos'][i] in ('WR', 'TE'))]+
                                 [-(opp_stack)*player_vars_id[qbid]]) >= 0
                                 
                                 
    ### Salary, position, rostersize
    prob += pulp.lpSum([points[f] * player_vars_id[f] for f in player_ids]) <= (maxpoints-0.01)
    
    prob += pulp.lpSum([costs[f] * player_vars_id[f] for f in player_ids]) <= max_budget
    prob += pulp.lpSum([costs[f] * player_vars_id[f] for f in player_ids]) >= min_budget
    
    prob += pulp.lpSum([player_vars_id[i] for i in player_ids]) == player_number
    
    prob += pulp.lpSum([low_owns[f] * player_vars_id[f] for f in player_ids]) >= 1
    
    prob += pulp.lpSum([rbs[f] * player_vars_id[f] for f in player_ids]) >= 2
    prob += pulp.lpSum([rbs[f] * player_vars_id[f] for f in player_ids]) <= 3
    
    prob += pulp.lpSum([qbs[f] * player_vars_id[f] for f in player_ids]) == 1
    
    prob += pulp.lpSum([wides[f] * player_vars_id[f] for f in player_ids]) >= 3
    prob += pulp.lpSum([wides[f] * player_vars_id[f] for f in player_ids]) <= 4
    
    #prob += pulp.lpSum([player_vars_id[i] for i in player_ids if df['pos'][i] == 'TE']) == 1
    prob += pulp.lpSum([tes[f] * player_vars_id[f] for f in player_ids]) == 1
    
    prob += pulp.lpSum([defs[f] * player_vars_id[f] for f in player_ids]) == 1
      
    ### SOLVE
    prob.solve()
       
    
    ### CREATE LINEUP
    lineup=[]
    print("Status:", pulp.LpStatus[prob.status])
    if pulp.LpStatus[prob.status]!= 'Optimal':
        return
    
    playercount=0
    for v in prob.variables():
        if v.varValue>0:           
            #print(player_items[int(v.name.split('_')[1])])
            lineup.append(player_items[int(v.name.split('_')[1])])
            playercount +=1
            if playercount >= player_number:
                break
    lineup.append(pulp.value(prob.objective))
    
    return lineup


### MAIN - create lineups

lineupdf=pd.DataFrame()

for lu in range(teams_create):
    lineup=optimize(df, opt_points)
    if lineup==None:
        print (lu,' finished - loosen ownerhsip number for more LUs')
        break
        
    opt_points=lineup[player_number]
    
    ### sort players to dk format
    dk_lu=['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'RB/WR/TE', 'DST']
    for i in range(len(dk_lu)):
        for y in range(len(lineup)-1):
            if df.loc[df['name']==lineup[y]]['pos'].values[0] in dk_lu[i] and df.loc[df['name']==lineup[y]]['player_id'].values[0] not in dk_lu:
                dk_lu[i]=int(df.loc[df['name']==lineup[y]]['player_id'].values[0])
                break
    ### manage ownership
    s = pd.Series(dk_lu)
    for i in range (len(s)):
        df.loc[df["player_id"] == s[i], "own_max"] -= 1
    df=df.loc[df["own_max"] > 0]
    df=df.reset_index(drop=True)
    
    ###print lineups
    print ('Lineup #', lu+1, ' ', lineup)
    lineupdf=lineupdf.append(s, ignore_index=True)


### STORE in .csv
lineupdf=lineupdf.astype(int)
lineupdf=lineupdf.astype(str)
lineupdf.loc[-1] = ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST']
lineupdf=lineupdf.sort_index()
lineupdf.to_csv('upload.csv',index=False, header=False)
 

### PRINT PLAYERS USED IN ALL LUS
players_used=lineupdf.stack().tolist()
players_used=pd.Series(players_used[9:])
players_used=players_used.reset_index(drop=True)
for i in range (len(players_used)):
    df_copy.loc[df_copy["player_id"] == players_used[i], "used"] += 1
print(df_copy[['name', 'pos', 'own_max','used']].to_string())