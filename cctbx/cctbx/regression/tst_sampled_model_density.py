from cctbx import xray
from cctbx import maptbx
from cctbx.development import random_structure
from cctbx.development import structure_factor_utils
from cctbx.development import debug_utils
from cctbx.array_family import flex
from scitbx import fftpack
import sys, os

def exercise(space_group_info, anomalous_flag, anisotropic_flag,
             d_min=1., resolution_factor=1./3, max_prime=5,
             quality_factor=100, wing_cutoff=1.e-3,
             exp_table_one_over_step_size=-100,
             force_complex=False,
             verbose=0):
  structure = random_structure.xray_structure(
    space_group_info,
    elements=("N", "C", "C", "O", "N", "C", "C", "O"),
    anisotropic_flag=anisotropic_flag,
    random_f_prime_d_min=1,
    random_f_double_prime=anomalous_flag
    )
  f_direct_array = structure.structure_factors_direct(
    anomalous_flag=anomalous_flag,
    d_min=d_min).f_calc_array()
  n_real = maptbx.determine_grid(
    unit_cell=f_direct_array.unit_cell(),
    d_min=d_min,
    resolution_factor=resolution_factor,
    max_prime=max_prime,
    mandatory_factors=f_direct_array.space_group().gridding())
  rfft = fftpack.real_to_complex_3d(n_real)
  u_extra = xray.calc_u_extra(d_min, resolution_factor, quality_factor)
  electron_density_must_be_positive = 1
  sampled_density = xray.sampled_model_density(
    structure.unit_cell(),
    structure.scatterers(),
    rfft.n_real(),
    rfft.m_real(),
    u_extra,
    wing_cutoff,
    exp_table_one_over_step_size,
    force_complex,
    electron_density_must_be_positive)
  assert sampled_density.anomalous_flag() == (anomalous_flag or force_complex)
  if (0 or verbose):
    print "number of scatterers passed:", \
      sampled_density.n_scatterers_passed()
    print "number of contributing scatterers:", \
      sampled_density.n_contributing_scatterers()
    print "number of anomalous scatterers:", \
      sampled_density.n_anomalous_scatterers()
    print "wing_cutoff:", sampled_density.wing_cutoff()
    print "exp_table_one_over_step_size:", \
      sampled_density.exp_table_one_over_step_size()
    print "exp_table_size:", sampled_density.exp_table_size()
    print "max_shell_radii:", sampled_density.max_shell_radii(),
    print "(%.4f, %.4f, %.4f)" % sampled_density.max_shell_radii_frac()
  tags = maptbx.grid_tags(rfft.n_real())
  symmetry_flags = maptbx.symmetry_flags(use_space_group_symmetry=True)
  tags.build(structure.space_group_info().type(), symmetry_flags)
  sampled_density.apply_symmetry(tags)
  if (not sampled_density.anomalous_flag()):
    map = sampled_density.real_map()
    assert map.all() == rfft.m_real()
    assert map.focus() == rfft.n_real()
    sf_map = rfft.forward(map)
    assert sf_map.all() == rfft.n_complex()
    assert sf_map.focus() == rfft.n_complex()
    collect_conj = 1
  else:
    cfft = fftpack.complex_to_complex_3d(rfft.n_real())
    map = sampled_density.complex_map()
    assert map.all() == cfft.n()
    assert map.focus() == cfft.n()
    sf_map = cfft.backward(map)
    assert sf_map.all() == cfft.n()
    assert sf_map.focus() == cfft.n()
    collect_conj = 0
  f_fft_data = maptbx.structure_factors.from_map(
    sampled_density.anomalous_flag(),
    f_direct_array.indices(),
    sf_map,
    collect_conj).data()
  sampled_density.eliminate_u_extra_and_normalize(
    f_direct_array.indices(),
    f_fft_data)
  structure_factor_utils.check_correlation(
    "direct/fft_regression", f_direct_array.indices(), 0,
    f_direct_array.data(), f_fft_data,
    min_corr_ampl=1*0.99, max_mean_w_phase_error=1*3.,
    verbose=verbose)
  f_fft_array = xray.structure_factors_fft(
    xray_structure=structure,
    miller_set=f_direct_array,
    grid_resolution_factor=resolution_factor,
    quality_factor=quality_factor,
    wing_cutoff=wing_cutoff,
    exp_table_one_over_step_size=exp_table_one_over_step_size,
    max_prime=max_prime).f_calc_array()
  structure_factor_utils.check_correlation(
    "direct/fft_xray", f_direct_array.indices(), 0,
    f_direct_array.data(), f_fft_array.data(),
    min_corr_ampl=1*0.99, max_mean_w_phase_error=1*3.,
    verbose=verbose)

def run_call_back(flags, space_group_info):
  for anomalous_flag in (False, True)[:]: #SWITCH
    for anisotropic_flag in (False, True)[:]: #SWITCH
      exercise(space_group_info, anomalous_flag, anisotropic_flag,
               verbose=flags.Verbose)

def run():
  debug_utils.parse_options_loop_space_groups(sys.argv[1:], run_call_back)

if (__name__ == "__main__"):
  run()
  t = os.times()
  print "u+s,u,s: %.2f %.2f %.2f" % (t[0] + t[1], t[0], t[1])
