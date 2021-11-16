"""
created: 2021
author: Bernardo Costa
email: bernamdc@gmail.com

"Nw" is short for "Nonhomogeneous wind" and is extensively used in this script
"""

import json
import numpy as np
from scipy import interpolate
from buffeting import U_bar_func, beta_0_func, RP, Pb_func
from mass_and_stiffness_matrix import stiff_matrix_func, stiff_matrix_12b_local_func, stiff_matrix_12c_local_func, linmass, SDL
from simple_5km_bridge_geometry import g_node_coor, p_node_coor, g_node_coor_func, R, arc_length, zbridge, bridge_shape, g_s_3D_func
from transformations import T_LsGs_3g_func, T_GsGw_func, from_cos_sin_to_0_2pi
from WRF_500_interpolated.create_minigrid_data_from_raw_WRF_500_data import n_bridge_WRF_nodes, bridge_WRF_nodes_coor_func, earth_R
import matplotlib.pyplot as plt


n_WRF_nodes = n_bridge_WRF_nodes
WRF_node_coor = g_node_coor_func(R=R, arc_length=arc_length, pontoons_s=[], zbridge=zbridge, FEM_max_length=arc_length/(n_WRF_nodes-1), bridge_shape=bridge_shape)  # needs to be calculated


# # Testing consistency between WRF nodes in bridge coordinates and in (lats,lons)
# test_WRF_node_consistency = True
# if test_WRF_node_consistency: # Make sure that the R and arc length are consistent in: 1) the bridge model and 2) WRF nodes (the arc along which WRF data is collected)
#     assert (R==5000 and arc_length==5000)
#     WRF_node_coor_2 = np.deg2rad(bridge_WRF_nodes_coor_func()) * earth_R
#     WRF_node_coor_2[:, 1] = -WRF_node_coor_2[:, 1]  # attention! bridge_WRF_nodes_coor_func() gives coor in (lats,lons) which is a left-hand system! This converts to right-hand (lats,-lons).
#     WRF_node_coor_2 = (WRF_node_coor_2 - WRF_node_coor_2[0]) @ np.array([[np.cos(np.deg2rad(-10)), -np.sin(np.deg2rad(-10))], [np.sin(np.deg2rad(-10)), np.cos(np.deg2rad(-10))]])
#     assert np.allclose(WRF_node_coor[:, :2], WRF_node_coor_2)


def interpolate_from_WRF_nodes_to_g_nodes(WRF_node_func, g_node_coor, WRF_node_coor, plot=False):
    """
    input:
    WRF_node_func.shape == (n_cases, n_WRF_nodes)
    output: shape (n_cases, n_g_nodes)
    Linear interpolation of a function known at the WRF_nodes, estimated at the g_nodes, assuming all nodes follow the same arc, along which the 1D interpolation dist is calculated
    This interpolation is made in 1D, along the along-arc distance s, otherwise the convex hull of WRF_nodes would not encompass the g_nodes and 2D extrapolations are not efficient / readily available
    """
    # Make sure the first and last g_nodes and WRF_nodes are positioned in the same place
    assert np.allclose(g_node_coor[0], WRF_node_coor[0])
    assert np.allclose(g_node_coor[-1], WRF_node_coor[-1])
    if plot:
        plt.scatter(g_node_coor[:, 0], g_node_coor[:, 1])
        plt.scatter(WRF_node_coor[:, 0], WRF_node_coor[:, 1], alpha=0.5, s=100)
        plt.axis('equal')
        plt.show()
    n_WRF_nodes = len(WRF_node_coor)
    n_g_nodes   = len(  g_node_coor)
    WRF_node_s = np.linspace(0, arc_length, n_WRF_nodes)
    g_node_s   = np.linspace(0, arc_length,   n_g_nodes)
    func = interpolate.interp1d(x=WRF_node_s, y=WRF_node_func, kind='linear')
    return func(g_node_s)


# # todo: delete below
# import copy
# from create_WRF_data_at_bridge_nodes_from_minigrid_data import wd_to_plot, ws_to_plot
# Nw_beta_DB_cos = interpolate_from_WRF_nodes_to_g_nodes(np.cos(wd_to_plot, dtype=float))
# Nw_beta_DB_sin = interpolate_from_WRF_nodes_to_g_nodes(np.sin(wd_to_plot, dtype=float))
# Nw_beta_DB = from_cos_sin_to_0_2pi(Nw_beta_DB_cos, Nw_beta_DB_sin, out_units='rad')
# Nw_beta_0 = np.array([beta_0_func(i) for i in Nw_beta_DB])
# print(np.rad2deg(Nw_beta_0))
# Nw_theta_0 = (copy.deepcopy(Nw_beta_0) * 0 + 1) * np.deg2rad(0)
# alpha = (copy.deepcopy(Nw_beta_0) * 0 + 1) *  np.deg2rad(0)
# # todo: delete above


def Nw_U_bar_func(g_node_coor, Nw_U_bar_at_WRF_nodes, force_Nw_U_and_N400_U_to_have_same=None):
    """
    Returns a vector of Nonhomogeneous mean wind at each of the g_nodes
    force_Nw_and_U_bar_to_have_same_avg : None, 'mean', 'energy'. force the Nw_U_bar_at_WRF_nodes to have the same e.g. mean 1, and thus when multiplied with U_bar, the result will have the same mean (of all nodes) wind
    """
    assert Nw_U_bar_at_WRF_nodes.shape[-1] == n_WRF_nodes
    U_bar_10min = U_bar_func(g_node_coor)
    interp_fun = interpolate_from_WRF_nodes_to_g_nodes(Nw_U_bar_at_WRF_nodes, g_node_coor, WRF_node_coor)
    if force_Nw_U_and_N400_U_to_have_same == 'mean':
        Nw_U_bar = U_bar_10min *        ( interp_fun / np.mean(interp_fun) )
        assert np.isclose(np.mean(Nw_U_bar), np.mean(U_bar_10min))        # same mean(U)
    elif force_Nw_U_and_N400_U_to_have_same == 'energy':
        Nw_U_bar = U_bar_10min * np.sqrt( interp_fun / np.mean(interp_fun) )
        assert np.isclose(np.mean(Nw_U_bar**2), np.mean(U_bar_10min**2))  # same energy = same mean(U**2)
    else:
        Nw_U_bar = interp_fun
    return Nw_U_bar

# Nw_U_bar_func(g_node_coor, Nw_U_bar_at_WRF_nodes=ws_to_plot, force_Nw_U_bar_and_U_bar_to_have_same=None)

def U_bar_equivalent_to_Nw_U_bar(g_node_coor, Nw_U_bar, force_Nw_U_bar_and_U_bar_to_have_same='energy'):
    """
    Nw_U_bar shape: (n_cases, n_nodes)
    Returns a homogeneous wind velocity field, equivalent to the input Nw_U_bar in terms of force_Nw_U_bar_and_U_bar_to_have_same
    force_Nw_U_bar_and_U_bar_to_have_same: None, 'mean', 'energy'. force the U_bar_equivalent to have the same mean or energy 1 as Nw_U_bar
    """
    if force_Nw_U_bar_and_U_bar_to_have_same is None:
        U_bar_equivalent = U_bar_func(g_node_coor)
    elif force_Nw_U_bar_and_U_bar_to_have_same == 'mean':
        U_bar_equivalent = np.ones(Nw_U_bar.shape) * np.mean(Nw_U_bar, axis=1)[:,None]
        assert all(np.isclose(np.mean(Nw_U_bar, axis=1)[:,None], np.mean(U_bar_equivalent, axis=1)[:,None]))
    elif force_Nw_U_bar_and_U_bar_to_have_same == 'energy':
        U_bar_equivalent = np.ones(Nw_U_bar.shape) * np.sqrt(np.mean(Nw_U_bar**2, axis=1)[:,None])
        assert all(np.isclose(np.mean(Nw_U_bar ** 2, axis=1)[:,None], np.mean(U_bar_equivalent ** 2, axis=1)[:,None]))  # same energy = same mean(U**2))
    return U_bar_equivalent


def Nw_beta_and_theta_bar_func(g_node_coor, Nw_beta_0, Nw_theta_0, alpha):
    """Returns the Nonhomogeneous beta_bar and theta_bar at each node, relative to the mean of the axes of the adjacent elements.
    Note: the mean of -179 deg and 178 deg should be 179.5 deg and not -0.5 deg. See: https://en.wikipedia.org/wiki/Mean_of_circular_quantities"""
    n_g_nodes = len(g_node_coor)
    assert len(Nw_beta_0) == len(Nw_theta_0) == n_g_nodes
    T_LsGs = T_LsGs_3g_func(g_node_coor, alpha)
    T_GsNw = np.array([T_GsGw_func(Nw_beta_0[i], Nw_theta_0[i]) for i in range(n_g_nodes)])
    T_LsNw = np.einsum('nij,njk->nik', T_LsGs, T_GsNw)
    U_Gw_norm = np.array([1, 0, 0])  # U_Gw = (U, 0, 0), so the normalized U_Gw_norm is (1, 0, 0)
    U_Ls = np.einsum('nij,j->ni', T_LsNw, U_Gw_norm)
    Ux = U_Ls[:, 0]
    Uy = U_Ls[:, 1]
    Uz = U_Ls[:, 2]
    Uxy = np.sqrt(Ux ** 2 + Uy ** 2)
    Nw_beta_bar = np.array([-np.arccos(Uy[i] / Uxy[i]) * np.sign(Ux[i]) for i in range(len(g_node_coor))])
    Nw_theta_bar = np.array([np.arcsin(Uz[i] / 1) for i in range(len(g_node_coor))])
    return Nw_beta_bar, Nw_theta_bar


def Nw_static_wind_func(g_node_coor, p_node_coor, alpha, Nw_U_bar, Nw_beta_0, Nw_theta_0, aero_coef_method='2D_fit_cons', n_aero_coef=6, skew_approach='3D'):
    """
    :return: New girder and gontoon node coordinates, as well as the displacements that led to them.
    """
    g_node_num = len(g_node_coor)
    p_node_num = len(p_node_coor)
    Nw_beta_bar, Nw_theta_bar = Nw_beta_and_theta_bar_func(g_node_coor, Nw_beta_0, Nw_theta_0, alpha)
    stiff_matrix = stiff_matrix_func(g_node_coor, p_node_coor, alpha)  # Units: (N)
    Pb = Pb_func(g_node_coor, Nw_beta_bar, Nw_theta_bar, alpha, aero_coef_method, n_aero_coef, skew_approach, Chi_Ci='ones')
    sw_vector = np.array([Nw_U_bar, np.zeros(len(Nw_U_bar)), np.zeros(len(Nw_U_bar))])  # instead of a=(u,v,w) a vector (U,0,0) is used.
    F_sw = np.einsum('ndi,in->nd', Pb, sw_vector) / 2  # Global buffeting force vector. See Paper from LD Zhu, eq. (24). Units: (N)
    F_sw_flat = np.ndarray.flatten(F_sw)  # flattening
    F_sw_flat = np.array(list(F_sw_flat) + [0]*len(p_node_coor)*6)  # adding 0 force to all the remaining pontoon DOFs
    # Global nodal Displacement matrix
    D_sw_flat = np.linalg.inv(stiff_matrix) @ F_sw_flat
    D_glob_sw = np.reshape(D_sw_flat, (g_node_num + p_node_num, 6))
    g_node_coor_sw = g_node_coor + D_glob_sw[:g_node_num,:3]  # Only the first 3 DOF are added as displacements. The 4th is alpha_sw
    p_node_coor_sw = p_node_coor + D_glob_sw[g_node_num:,:3]  # Only the first 3 DOF are added as displacements. The 4th is alpha_sw
    return g_node_coor_sw, p_node_coor_sw, D_glob_sw


def get_ANN_Z2_preds(ANN_Z1_preds, EN_Z1_preds, EN_Z2_preds):
    """
    inputs with special format: dict of (points) dicts of ('sector' & 'Iu') lists of floats

    Get the Artificial Neural Network predictions of Iu at a new height above sea level Z2, using a transfer function from different EN-1991-1-4 predictions at both Z1 and Z2.
    The transfer function is just a number for each mean wind direction (it varies with wind direction between e.g. 1.14 and 1.30, for Z1=48m to Z2=14.5m)

    Details:
    Converting ANN preds from Z1=48m, to Z2=14.5m, requires log(Z1/z0)/log(Z2/z0), but z0 depends on terrain roughness which is inhomogeneous and varies with wind direction. Solution: Predict Iu
    using the EN1991 at both Z1 and Z2 (using the "binary-geneous" terrain roughnesses), and find the transfer function between Iu(Z2) and Iu(Z1), for each wind direction, and apply to ANN preds.

    Try:
    from sympy import Symbol, simplify, ln
    z1 = Symbol('z1', real=True, positive=True)
    z2 = Symbol('z2', real=True, positive=True)
    c = Symbol('c', real=True, positive=True)
    z0 = Symbol('z0', real=True, positive=True)
    Iv1 = c / ln(z1 / z0)  # c is just a constant. It assumes Iu(Z) = sigma_u / Vm(Z), where sigma_u is independent of Z, and where Vm depends only on cr(Z), which depends on ln(Z / z0)
    Iv2 = c / ln(z2 / z0)
    simplify(Iv2 / Iv1)
    """
    ANN_Z2_preds = {}
    for point in list(ANN_Z1_preds.keys()):
        assert ANN_Z1_preds[point]['sector'] == EN_Z1_preds[point]['sector'] == EN_Z2_preds[point]['sector'] == np.arange(360).tolist(), 'all inputs must have all 360 directions!'
        Iu_ANN_Z2 = np.array(ANN_Z1_preds[point]['Iu']) * (np.array(EN_Z2_preds[point]['Iu']) / np.array(EN_Z1_preds[point]['Iu']))
        ANN_Z2_preds[point] = {'sector':ANN_Z1_preds[point]['sector'], 'Iu':Iu_ANN_Z2.tolist()}
    return ANN_Z2_preds

def Nw_Iu_all_dirs_database(model='ANN', use_existing_file=True):
    """
    This function is simple but got a bit confusing in the process with too much copy paste...
    model: 'ANN' or 'EN'
    use_existing_file: False should be used when we have new g_node_num!!
    Returns an array of Iu with shape (n_g_nodes, n_dirs==360)
    """
    assert zbridge == 14.5, "ERROR: zbridge!=14.5m. You must produce new Iu_EN_preds at the correct Z. Go to MetOcean project and replace all '14m' by desired Z. Copy the new json files to this project "

    if model == 'ANN':
        if not use_existing_file:
            # Then there must exist 3 other necessary files (at each WRF node) that will be used to create and store the desired file (at each girder node)
            with open(r"intermediate_results\\Nw_Iu\\Iu_48m_ANN_preds.json") as f:
                dict_Iu_48m_ANN_preds = json.loads(f.read())
            with open(r"intermediate_results\\Nw_Iu\\Iu_48m_EN_preds.json") as f:
                dict_Iu_48m_EN_preds = json.loads(f.read())
            with open(r"intermediate_results\\Nw_Iu\\Iu_14m_EN_preds.json") as f:
                dict_Iu_14m_EN_preds = json.loads(f.read())
            dict_Iu_14m_ANN_preds = get_ANN_Z2_preds(ANN_Z1_preds=dict_Iu_48m_ANN_preds, EN_Z1_preds=dict_Iu_48m_EN_preds, EN_Z2_preds=dict_Iu_14m_EN_preds)
            Iu_14m_ANN_preds_WRF = np.array([dict_Iu_14m_ANN_preds[k]['Iu'] for k in dict_Iu_14m_ANN_preds.keys()]).T  # calculated at 11 WRF nodes
            Iu_14m_ANN_preds = interpolate_from_WRF_nodes_to_g_nodes(Iu_14m_ANN_preds_WRF, g_node_coor, WRF_node_coor, plot=False)  # calculated at the girder nodes
            Iu_14m_ANN_preds = Iu_14m_ANN_preds.T
            # Storing
            with open(r'intermediate_results\\Nw_Iu\\Iu_14m_ANN_preds_g_nodes.json', 'w', encoding='utf-8') as f:
                json.dump(Iu_14m_ANN_preds.tolist(), f, ensure_ascii=False, indent=4)
        else:
            with open(r'intermediate_results\\Nw_Iu\\Iu_14m_ANN_preds_g_nodes.json') as f:
                Iu_14m_ANN_preds = np.array(json.loads(f.read()))
        return Iu_14m_ANN_preds
    elif model =='EN':
        if not use_existing_file:
            with open(r"intermediate_results\\Nw_Iu\\Iu_14m_EN_preds.json") as f:
                dict_Iu_14m_EN_preds = json.loads(f.read())
            Iu_14m_EN_preds_WRF = np.array([dict_Iu_14m_EN_preds[k]['Iu'] for k in dict_Iu_14m_EN_preds.keys()]).T  # calculated at 11 WRF nodes
            Iu_14m_EN_preds = interpolate_from_WRF_nodes_to_g_nodes(Iu_14m_EN_preds_WRF, g_node_coor, WRF_node_coor, plot=False)  # calculated at the girder nodes
            Iu_14m_EN_preds = Iu_14m_EN_preds.T
            # Storing
            with open(r'intermediate_results\\Nw_Iu\\Iu_14m_EN_preds_g_nodes.json', 'w', encoding='utf-8') as f:
                json.dump(Iu_14m_EN_preds.tolist(), f, ensure_ascii=False, indent=4)
        else:
            with open(r'intermediate_results\\Nw_Iu\\Iu_14m_EN_preds_g_nodes.json') as f:
                Iu_14m_EN_preds = np.array(json.loads(f.read()))
        return Iu_14m_EN_preds
# Creating a database when importing this nonhomogeneity.py file! This will be run only once, when this file is imported, so that the correct g_node_num is used to create the database!
Nw_Iu_all_dirs_database(model='ANN', use_existing_file=False)
Nw_Iu_all_dirs_database(model='EN', use_existing_file=False)

def Nw_Ii_func(Nw_beta_DB, model='ANN'):
    """
    For computer efficiency, nearest neighbour is used (instead of linear inerpolation), assuming 360 directions in the database
    Nw_beta_DB: len == n_g_nodes
    Returns: array that describes Iu, Iv, Iw at each g node, with shape (n_nodes, 3)
    """
    Iu = Nw_Iu_all_dirs_database(model=model, use_existing_file=True)
    assert Iu.shape[-1] == 360, "360 directions assumed in the database. If not, the code changes substantially"
    dir_idxs = np.rint(np.rad2deg(Nw_beta_DB)).astype(int)
    dir_idxs[dir_idxs==360] = 0  # in case a direction is assumed to be 360, convert it to 0
    Iu = np.array([Iu[n,d] for n,d in enumerate(dir_idxs)])
    Iv =  # see Design Basis
    Iw =  # see Design Basis
    return


def Nw_S_a_func():
    pass


def Nw_S_aa_func():
    pass



