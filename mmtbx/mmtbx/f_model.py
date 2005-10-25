from cctbx.array_family import flex
import math, time
from cctbx import miller
from cctbx import crystal
from cctbx import adptbx
from scitbx import lbfgs
from libtbx import adopt_init_args
from libtbx.test_utils import approx_equal, not_approx_equal
from mmtbx import bulk_solvent
from mmtbx import masks
from cctbx import xray
from mmtbx import max_lik
from mmtbx.max_lik import maxlik
from mmtbx.refinement import print_statistics
from cctbx.eltbx.xray_scattering import wk1995
from mmtbx.max_lik import max_like_non_uniform
import mmtbx.bulk_solvent.bulk_solvent_and_scaling as bss
import sys, random
from cctbx import miller
import cctbx.xray.structure_factors
from cctbx.array_family import flex
from stdlib import math
from cctbx import xray
from cctbx import adptbx

class core_arrays(object):
  def __init__(self, f_obs               = None,
                     f_calc              = None,
                     abcd                = None,
                     f_mask              = None,
                     alpha               = None,
                     beta                = None,
                     flags               = None):
    adopt_init_args(self, locals())


class manager(object):
  def __init__(self, f_obs               = None,
                     r_free_flags        = None,
                     u_aniso             = [0.,0.,0.,0.,0.,0.],
                     k_sol               = 0.0,
                     b_sol               = 0.0,
                     sf_algorithm        = "fft",
                     sf_cos_sin_table    = True,
                     target_name         = None,
                     abcd                = None,
                     alpha_beta_params   = None,
                     xray_structure      = None,
                     f_mask              = None,
                     mask_params         = None,
                     log                 = None):
    adopt_init_args(self, locals())
    if (self.log is None): self.log = sys.stdout
    assert self.f_obs is not None
    assert self.f_obs.is_real_array()
    assert self.xray_structure is not None
    assert len(self.u_aniso) == 6
    if(self.r_free_flags is not None):
       assert self.r_free_flags.indices().all_eq(self.f_obs.indices()) == 1
    if(self.f_mask is not None):
       assert self.f_mask.indices().all_eq(self.f_obs.indices()) == 1
    if(self.abcd is not None):
       assert self.abcd.indices().all_eq(self.f_obs.indices()) == 1
    assert self.sf_algorithm in ("fft", "direct")
    self.target_names = (
      "ls_wunit_k1","ls_wunit_k2","ls_wunit_kunit","ls_wunit_k1_fixed",
      "ls_wunit_k1ask3_fixed",
      "ls_wexp_k1" ,"ls_wexp_k2" ,"ls_wexp_kunit",
      "ls_wff_k1"  ,"ls_wff_k2"  ,"ls_wff_kunit","ls_wff_k1_fixed",
      "ls_wff_k1ask3_fixed",
      "lsm_k1"     ,"lsm_k2"    ,"lsm_kunit","lsm_k1_fixed","lsm_k1ask3_fixed",
      "ml","mlhl")
    if(self.target_name is not None):
       assert self.target_name in self.target_names
       self.setup_target_functors()
    if(self.f_mask is None):
       self.f_mask = \
          self.f_obs.array(data = flex.complex_double(self.f_obs.data().size(),0.))
    self.f_ordered_solvent = \
      self.f_obs.array(data = flex.complex_double(self.f_obs.data().size(),0.))
    self.f_ordered_solvent_dist = \
      self.f_obs.array(data = flex.complex_double(self.f_obs.data().size(),0.))
    self.n_ordered_water = 0.0
    self.b_ordered_water = 0.0
    self.update_xray_structure(self.xray_structure,
                               update_f_calc = True,
                               update_f_mask = False)

  def deep_copy(self):
    if(self.abcd is not None):
       abcd = self.abcd.deep_copy()
    else:
       abcd = None
    new=manager(f_obs             = self.f_obs.deep_copy(),
                r_free_flags      = self.r_free_flags.deep_copy(),
                u_aniso           = self.u_aniso,
                k_sol             = self.k_sol,
                b_sol             = self.b_sol,
                sf_algorithm      = self.sf_algorithm,
                sf_cos_sin_table  = self.sf_cos_sin_table,
                target_name       = self.target_name,
                abcd              = abcd,
                alpha_beta_params = self.alpha_beta_params,
                xray_structure    = self.xray_structure.deep_copy_scatterers(),
                mask_params       = self.mask_params,
                log               = self.log)
    new.f_calc                 = self.f_calc.deep_copy()
    new.f_mask                 = self.f_mask.deep_copy()
    new.f_ordered_solvent      = self.f_ordered_solvent.deep_copy()
    new.f_ordered_solvent_dist = self.f_ordered_solvent_dist.deep_copy()
    new.n_ordered_water        = self.n_ordered_water
    new.b_ordered_water        = self.b_ordered_water
    return new

  def resolution_filter(self, d_max = None, d_min = None):
    dc = self.deep_copy()
    if(dc.abcd  is not None):
       abcd = dc.abcd.resolution_filter(d_max, d_min)
    else:
       abcd = None
    new  = manager(f_obs             = dc.f_obs.resolution_filter(d_max, d_min),
                   r_free_flags      = dc.r_free_flags.resolution_filter(d_max, d_min),
                   u_aniso           = dc.u_aniso,
                   k_sol             = dc.k_sol,
                   b_sol             = dc.b_sol,
                   sf_algorithm      = dc.sf_algorithm       ,
                   target_name       = dc.target_name        ,
                   abcd              = abcd               ,
                   alpha_beta_params = dc.alpha_beta_params  ,
                   xray_structure    = dc.xray_structure     ,
                   mask_params       = dc.mask_params        ,
                   log               = dc.log                )
    new.f_calc                 = dc.f_calc.resolution_filter(d_max, d_min)
    new.f_mask                 = dc.f_mask.resolution_filter(d_max, d_min)
    new.f_ordered_solvent      = dc.f_ordered_solvent.resolution_filter(d_max, d_min)
    new.f_ordered_solvent_dist = dc.f_ordered_solvent_dist.resolution_filter(d_max, d_min)
    new.n_ordered_water        = dc.n_ordered_water
    new.b_ordered_water        = dc.b_ordered_water
    return new

  def apply_back_b_iso(self):
    #r_work_1 = self.r_work()
    b_iso = self.u_iso()
    u_aniso = self.u_aniso
    u_aniso_new = [u_aniso[0]-b_iso,u_aniso[1]-b_iso,u_aniso[2]-b_iso,
                   u_aniso[3],      u_aniso[4],      u_aniso[5]]
    self.u_aniso = u_aniso_new
    b_sol = self.k_sol_b_sol()[1] + b_iso
    if(b_sol > 80.0): b_sol = 80.0
    if(b_sol < 10.0): b_sol = 10.0
    self.b_sol = b_sol
    self.xray_structure.shift_us(b_shift = b_iso)
    self.xray_structure.tidy_us(u_min = 1.e-6)
    self.f_calc = self.f_obs.structure_factors_from_scatterers(
      xray_structure = self.xray_structure,
      algorithm      = self.sf_algorithm,
      cos_sin_table  = self.sf_cos_sin_table).f_calc()
    #r_work_2 = fmodel.r_work()

  def set_f_ordered_solvent(self, params):
    if(params.nu_fix_b_atoms is not None):
       self.n_ordered_water = params.nu_fix_n_atoms
       self.b_ordered_water = params.nu_fix_b_atoms
       self.f_ordered_solvent = max_like_non_uniform.f_ordered_solvent(
                            f                    = self.f_ordered_solvent_dist,
                            n_water_atoms_absent = self.n_ordered_water,
                            bf_atoms_absent      = self.b_ordered_water,
                            absent_atom_type     = "O")
    else:
       r = self.target_w()
       f_ordered_solvent = self.f_ordered_solvent
       n_ordered_water   = self.n_ordered_water
       b_ordered_water   = self.b_ordered_water
       n_atoms_prot = self.xray_structure.scatterers().size()
       n_residues = n_atoms_prot / 10
       n_solvent_max = n_residues * 2
       n_solvent_min = n_residues / 2
       u_isos = self.xray_structure.extract_u_iso_or_u_equiv()
       b_iso_mean = flex.mean(u_isos * math.pi**2*8)
       b_solvent_max = int(b_iso_mean + 35.0)
       b_solvent_min = int(b_iso_mean - 5.0)
       for n in range(n_solvent_min, n_solvent_max+1, 10):
           for b in range(b_solvent_min, b_solvent_max+1, 5):
               self.f_ordered_solvent = max_like_non_uniform.f_ordered_solvent(
                            f                    = self.f_ordered_solvent_dist,
                            n_water_atoms_absent = n,
                            bf_atoms_absent      = b,
                            absent_atom_type     = "O")
               r_i = self.target_w()
               if(r_i < r):
                  r = r_i
                  f_ordered_solvent = self.f_ordered_solvent
                  n_ordered_water = n
                  b_ordered_water = b
       self.n_ordered_water = n_ordered_water
       self.b_ordered_water = b_ordered_water
       self.f_ordered_solvent = f_ordered_solvent
       assert approx_equal(self.target_w(), r)
       ############## ????
       self.alpha_beta_params.n_water_atoms_absent = self.n_ordered_water
       self.alpha_beta_params.bf_atoms_absent = self.b_ordered_water


  def update_xray_structure(self,
                            xray_structure,
                            update_f_calc = False,
                            update_f_mask = False,
                            update_f_ordered_solvent = False):
    self.xray_structure = xray_structure
    if(self.mask_params is not None):
       step = self.f_obs.d_min()/self.mask_params.grid_step_factor
    else:
       step = self.f_obs.d_min() / 4.0
    if(step < 0.3): step = 0.3
    if(update_f_ordered_solvent): step = 0.3
    if(update_f_calc):
       self.f_calc = self.f_obs.structure_factors_from_scatterers(
         xray_structure = self.xray_structure,
         algorithm      = self.sf_algorithm,
         cos_sin_table  = self.sf_cos_sin_table).f_calc()
    if(update_f_ordered_solvent):
       nu_manager = max_like_non_uniform.ordered_solvent_distribution(
                                               structure = self.xray_structure,
                                               fo        = self.f_obs,
                                               grid_step = step,
                                               rad       = 0.0)
       nu_map = nu_manager.distribution_as_array()
       self.f_ordered_solvent_dist = nu_manager.fcalc_from_distribution()
       ########################################################################
       #selection = self.f_ordered_solvent_dist.d_spacings().data() <= 3.5
       #print selection.count(True), selection.count(False)
       #data = self.f_ordered_solvent_dist.data()
       #data.set_selected(selection, 0.0)
       #self.f_ordered_solvent_dist.array(data = data)
       ########################################################################
    if(update_f_mask):
       if(update_f_ordered_solvent == False): nu_map = None
       bulk_solvent_mask_obj = self.bulk_solvent_mask()
       if (nu_map is not None):
         bulk_solvent_mask_obj.subtract_non_uniform_solvent_region_in_place(
                                                     non_uniform_mask = nu_map)
       if(self.mask_params is not None and self.mask_params.verbose > 0):
          bulk_solvent_mask_obj.show_summary(out = self.log)
       self.f_mask = \
                 bulk_solvent_mask_obj.structure_factors(miller_set=self.f_obs)

  def bulk_solvent_mask(self):
    if(self.mask_params is not None):
       step = self.f_obs.d_min()/self.mask_params.grid_step_factor
    else:
       step = self.f_obs.d_min() / 4.0
    if(self.mask_params is not None):
       result = masks.bulk_solvent(
          xray_structure           = self.xray_structure,
          grid_step                = step,
          solvent_radius           = self.mask_params.solvent_radius,
          shrink_truncation_radius = self.mask_params.shrink_truncation_radius)
    else:
       result = masks.bulk_solvent(xray_structure = self.xray_structure,
                                   grid_step      = step)
    return result

  def update_solvent_and_scale(self, params = None):
    if(self.k_sol == 0.0):
       flag_1 = False
       flag_2 = True
    else:
       flag_1 = True
       flag_2 = False
    if(0 and flag_1):
       r_start = self.r_free()
       fmodel_copy = self.deep_copy()
       step = self.f_obs.d_min()/self.mask_params.grid_step_factor
       for r_solv in (0.8,0.9,1.0,1.1,1.2):
           for r_shrink in (0.8,0.9,1.0,1.1,1.2):
               bulk_solvent_mask = masks.bulk_solvent(
                  xray_structure           = self.xray_structure,
                  grid_step                = step,
                  solvent_radius           = r_solv,
                  shrink_truncation_radius = r_shrink)
               f_mask = bulk_solvent_mask.structure_factors(miller_set=self.f_obs)
               fmodel_copy.update(f_mask = f_mask)
               r = fmodel_copy.r_free()
               if(r < r_start):
                  r_start = r
                  self.mask_params.solvent_radius = r_solv
                  self.mask_params.shrink_truncation_radius = r_shrink
                  self.f_mask = self.f_mask.array(data = f_mask.data())
                  assert fmodel_copy.r_work() == self.r_work()
                  if(self.mask_params is not None and self.mask_params.verbose > 0):
                     print r
                     bulk_solvent_mask.show_summary(out = self.log)
    if(params is None):
       params = bss.solvent_and_scale_params()
    else:
       params = bss.solvent_and_scale_params(overwrite = params)
    to_do = [params.bulk_solvent_correction, params.anisotropic_scaling,
                                              params.statistical_solvent_model]
    if(to_do.count(False) != 3):
       target_name_start = params.target
       save_fmodel_target = self.target_name
       if(self.alpha_beta_params is not None):
          save_interpolation_flag = self.alpha_beta_params.interpolation
          self.alpha_beta_params.interpolation = False
       else:
          save_interpolation_flag = False
       if(target_name_start == "ml"): params.target = "ls_wunit_k1"
       to_do = [params.bulk_solvent_correction, params.anisotropic_scaling,
                                              params.statistical_solvent_model]
       if(to_do == [False,False,True]): params.target = target_name_start
       self.update(target_name = params.target)
       m="macro_cycle= "
       minimization_macro_cycles = \
                         range(1, params.number_of_minimization_macro_cycles+1)
       max_of_f_mask = flex.max(flex.abs(self.f_mask.data()))
       min_of_f_mask = flex.min(flex.abs(self.f_mask.data()))
       if(params.bulk_solvent_correction):
          assert max_of_f_mask - min_of_f_mask > 1.e-6
       target_start  = self.target_w()
       k_sol_start   = self.k_sol
       b_sol_start   = self.b_sol
       u_aniso_start = self.u_aniso
       macro_cycles = range(1, params.number_of_macro_cycles+1)
       if(params.k_sol_b_sol_grid_search):
          k_sols =kb_range(params.k_sol_max,params.k_sol_min,params.k_sol_step)
          b_sols =kb_range(params.b_sol_max,params.b_sol_min,params.b_sol_step)
       if(params.verbose > 0):
          self.show_k_sol_b_sol_u_aniso_target(header = m+str(0)+\
                                          " (start) target= "+self.target_name)
       if(params.fix_k_sol is not None):
          self.update(k_sol = params.fix_k_sol,
                      b_sol = params.fix_b_sol)
       if(params.fix_u_aniso is not None):
          self.update(u_aniso = params.fix_u_aniso)
       if(to_do.count(False) == 2):
          macro_cycles = range(1,2)
       if((params.k_sol_b_sol_grid_search,params.minimization_k_sol_b_sol) == \
                                                                 (False,True)):
           fmodel_copy = self.deep_copy()
           fmodel_copy.update(k_sol = params.start_minimization_from_k_sol,
                              b_sol = params.start_minimization_from_b_sol,
                              u_aniso = params.start_minimization_from_u_aniso)
       for mc in macro_cycles:
           if(params.k_sol_b_sol_grid_search):
              for self.k_sol in k_sols:
                  for self.b_sol in b_sols:
                      target = self.target_w()
                      if(target < target_start):
                         target_start = target
                         k_sol_start  = self.k_sol
                         b_sol_start  = self.b_sol
              self.k_sol = k_sol_start
              self.b_sol = b_sol_start
              if(params.verbose > 0):
                 h=m+str(mc)+": k & b: grid search; T= "+self.target_name
                 self.show_k_sol_b_sol_u_aniso_target(header = h)
           if((params.k_sol_b_sol_grid_search,params.minimization_k_sol_b_sol)\
                                                              == (False,True)):
              self.k_sol, self.b_sol = bss.k_sol_b_sol_minimizer(fmodel = \
                                                                   fmodel_copy)
              fmodel_copy = self
              if(params.verbose > 0):
                 h=m+str(mc)+": k & b: minimization; T= "+self.target_name
                 self.show_k_sol_b_sol_u_aniso_target(header = h)
           if(params.minimization_u_aniso):
              self._u_aniso_minimizer_helper(params, mc)
           if(params.statistical_solvent_model):
              self.set_f_ordered_solvent(params = params)
              target = self.target_w()
              if(target > target_start):
                 print "ordered solvent: T start=, end= ",target_start,target
              target_start = target
              if(params.verbose > 0):
                 h=m+str(mc)+": (ordered solvent) T= "+self.target_name
                 self.show_k_sol_b_sol_u_aniso_target(header = h)
       for mc in minimization_macro_cycles:
           if(params.minimization_k_sol_b_sol):
              self._k_sol_b_sol_minimization_helper(params, mc)
           if(params.minimization_u_aniso):
              self._u_aniso_minimizer_helper(params, mc)
       ### start ml optimization
       if(abs(self.k_sol) < 1.e-2):
          self.k_sol = 0.0
          self.b_sol = 0.0
       self.update(target_name = save_fmodel_target)
       if(target_name_start == "ml"):
          params.target = "ml"
          save_fmodel_target = self.target_name
          self.update(target_name = "ml")
          save_k_sol = self.k_sol
          save_b_sol = self.b_sol
          if(params.minimization_k_sol_b_sol):
             for mc in minimization_macro_cycles:
                 if(params.verbose > 0):
                    h=m+str(0)+": start k&b minimization; T= "+self.target_name
                    self.show_k_sol_b_sol_u_aniso_target(header = h)
                 self._k_sol_b_sol_minimization_helper(params, mc)
          self.update(target_name = save_fmodel_target)
          if(self.alpha_beta_params is not None):
             self.alpha_beta_params.interpolation = save_interpolation_flag
       if(params.apply_back_trace_of_u_aniso and abs(self.u_iso()) > 0.0):
          self.apply_back_b_iso()
          if(params.verbose > 0):
             h=m+str(mc)+": apply back trace of u_aniso: T= "+self.target_name
             self.show_k_sol_b_sol_u_aniso_target(header = h)
    if(abs(self.k_sol) < 1.e-2 or abs(self.b_sol) < 1.e-2):
       self.k_sol = 0.0
       self.b_sol = 0.0
    if(0 and flag_2):
       r_start = self.r_free()
       fmodel_copy = self.deep_copy()
       step = self.f_obs.d_min()/self.mask_params.grid_step_factor
       for r_solv in (0.8,0.9,1.0,1.1,1.2):
           for r_shrink in (0.8,0.9,1.0,1.1,1.2):
               bulk_solvent_mask = masks.bulk_solvent(
                  xray_structure           = self.xray_structure,
                  grid_step                = step,
                  solvent_radius           = r_solv,
                  shrink_truncation_radius = r_shrink)
               f_mask = bulk_solvent_mask.structure_factors(miller_set=self.f_obs)
               fmodel_copy.update(f_mask = f_mask)
               r = fmodel_copy.r_free()
               if(r < r_start):
                  r_start = r
                  self.mask_params.solvent_radius = r_solv
                  self.mask_params.shrink_truncation_radius = r_shrink
                  self.f_mask = self.f_mask.array(data = f_mask.data())
                  assert fmodel_copy.r_work() == self.r_work()
                  if(self.mask_params is not None and self.mask_params.verbose > 0):
                     print r
                     bulk_solvent_mask.show_summary(out = self.log)

  def _u_aniso_minimizer_helper(self, params, mc):
    m="macro_cycle= "
    symm_constr = params.symmetry_constraints_on_u_aniso
    u_cycles = range(1, params.number_of_cycles_for_anisotropic_scaling+1)
    target_start = self.target_w()
    for u_cycle in u_cycles:
        self.u_aniso = bss.aniso_scale_minimizer(fmodel      = self,
                                                 symm_constr = symm_constr)
    target_final = self.target_w()
    diff = abs(abs(target_final) - abs(target_start))
    if(target_start < target_final and diff > 1.e-7):
       print "u_aniso search: T start=, final= ",target_start,target_final
    if(params.verbose > 0):
       h=m+str(mc)+": anisotropic scale; T= "+self.target_name
       self.show_k_sol_b_sol_u_aniso_target(header = h)

  def _k_sol_b_sol_minimization_helper(self, params, mc):
    m="macro_cycle= "
    self.k_sol,self.b_sol= bss.k_sol_b_sol_minimizer(fmodel = self)
    if(params.verbose > 0):
       h=m+str(mc)+": (k_sol & b_sol minimization) T= "+self.target_name
       self.show_k_sol_b_sol_u_aniso_target(header = h)
    reset_k_sol_b_sol_flag = 0
    if(self.k_sol <= params.k_sol_min or self.k_sol >= params.k_sol_max):
       k1 = abs(abs(self.k_sol) - abs(params.k_sol_min))
       k2 = abs(abs(self.k_sol) - abs(params.k_sol_max))
       if(k1 >= k2): self.k_sol = params.k_sol_max
       if(k1 <= k2): self.k_sol = params.k_sol_min
       reset_k_sol_b_sol_flag = 1
    if(self.b_sol <= params.b_sol_min or self.b_sol >= params.b_sol_max):
       b1 = abs(abs(self.b_sol) - abs(params.b_sol_min))
       b2 = abs(abs(self.b_sol) - abs(params.b_sol_max))
       if(b1 >= b2): self.b_sol = params.b_sol_max
       if(b1 <= b2): self.b_sol = params.b_sol_min
       reset_k_sol_b_sol_flag = 1
    if(params.verbose > 0 and reset_k_sol_b_sol_flag == 1):
       h=m+str(mc)+": (k_sol & b_sol reset: values out of range) T= "+\
                                                               self.target_name
       self.show_k_sol_b_sol_u_aniso_target(header = h)


  def setup_target_functors(self):
    if(self.target_name == "ml"):
       self.target_functors = xray.target_functors.target_functors_manager(
                                        target_name = self.target_name,
                                        f_obs       = self.f_obs,
                                        flags       = self.r_free_flags.data())
    if(self.target_name == "mlhl"):
       assert self.abcd is not None
       self.target_functors = xray.target_functors.target_functors_manager(
                                        target_name = self.target_name,
                                        f_obs       = self.f_obs,
                                        flags       = self.r_free_flags.data(),
                                        abcd        = self.abcd)
    if(self.target_name == "ls_wunit_k1"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = flex.double(self.f_obs.data().size(), 1.0))
    if(self.target_name == "ls_wunit_k1_fixed"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = flex.double(self.f_obs.data().size(), 1.0),
                     scale_factor = self.scale_k1_w())
    if(self.target_name == "ls_wunit_k2"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = flex.double(self.f_obs.data().size(), 1.0))
    if(self.target_name == "ls_wunit_kunit"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = flex.double(self.f_obs.data().size(), 1.0),
                     scale_factor = 1.0)
    if(self.target_name == "ls_wunit_k1ask3_fixed"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = flex.double(self.f_obs.data().size(), 1.0),
                     scale_factor = self.scale_k3_w())
    if(self.target_name == "ls_wexp_k1"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = ls_sigma_weights(self.f_obs))
    if(self.target_name == "ls_wexp_k2"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = ls_sigma_weights(self.f_obs))
    if(self.target_name == "ls_wexp_kunit"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = ls_sigma_weights(self.f_obs),
                     scale_factor = 1.0)
    if(self.target_name == "ls_wff_k1"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = ls_ff_weights(self.f_obs, "N", 25.0))
    if(self.target_name == "ls_wff_k1_fixed"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = ls_ff_weights(self.f_obs, "N", 25.0),
                     scale_factor = self.scale_k1_w())
    if(self.target_name == "ls_wff_k1ask3_fixed"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = ls_ff_weights(self.f_obs, "N", 25.0),
                     scale_factor = self.scale_k3_w())
    if(self.target_name == "ls_wff_k2"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = ls_ff_weights(self.f_obs, "N", 25.0))
    if(self.target_name == "ls_wff_kunit"):
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = self.f_obs,
                     flags        = self.r_free_flags.data(),
                     weights      = ls_ff_weights(self.f_obs, "N", 25.0),
                     scale_factor = 1.0)
    if(self.target_name == "lsm_k1"):
       f_star, w_star = self.f_star_w_star()
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = f_star,
                     flags        = self.r_free_flags.data(),
                     weights      = w_star.data())
    if(self.target_name == "lsm_k1ask3_fixed"):
       f_star, w_star = self.f_star_w_star()
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = f_star,
                     flags        = self.r_free_flags.data(),
                     weights      = w_star.data(),
                     scale_factor = self.scale_k3_w())
    if(self.target_name == "lsm_k1_fixed"):
       f_star, w_star = self.f_star_w_star()
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = f_star,
                     flags        = self.r_free_flags.data(),
                     weights      = w_star.data(),
                     scale_factor = self.scale_k1_w())
    if(self.target_name == "lsm_k2"):
       f_star, w_star = self.f_star_w_star()
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = f_star,
                     flags        = self.r_free_flags.data(),
                     weights      = w_star.data())
    if(self.target_name == "lsm_kunit"):
       f_star, w_star = self.f_star_w_star()
       self.target_functors = xray.target_functors.target_functors_manager(
                     target_name  = self.target_name,
                     f_obs        = f_star,
                     flags        = self.r_free_flags.data(),
                     weights      = w_star.data(),
                     scale_factor = 1.0)
    self.target_functor_w = self.target_functors.target_functor_w()
    self.target_functor_t = self.target_functors.target_functor_t()

  def xray_target_functor_result(self, compute_gradients = None,
                                       alpha             = None,
                                       beta              = None,
                                       scale_ml          = None,
                                       flag              = None):
    assert compute_gradients in (True,False)
    assert flag in ("work", "test")
    if(flag == "work"):
       f_model = self.f_model_w()
       if(self.target_name in ("ml","mlhl")):
          if(alpha is None and beta is None):
             alpha, beta = self.alpha_beta_w()
          else:
             assert alpha.data().size() == f_model.data().size()
             assert beta.data().size() == f_model.data().size()
          if(scale_ml is None):
             if(self.alpha_beta_params is not None):
                if(self.alpha_beta_params.method == "calc"):
                   if(self.alpha_beta_params.fix_scale_for_calc_option is None):
                      scale_ml = self.scale_ml()
                   else:
                      scale_ml=self.alpha_beta_params.fix_scale_for_calc_option
                else:
                   scale_ml = 1.0
             else:
                scale_ml = 1.0
          return self.target_functor_w(f_model,
                                       alpha.data(),
                                       beta.data(),
                                       scale_ml,
                                       compute_gradients)
       if(self.target_name.count("ls") == 1):
          alpha is None and beta is None
          return self.target_functor_w(f_model, compute_gradients)
    if(flag == "test"):
       f_model = self.f_model_t()
       if(self.target_name in ("ml","mlhl")):
          if(alpha is None and beta is None):
             alpha, beta = self.alpha_beta_t()
          else:
             assert alpha.data().size() == f_model.data().size()
             assert beta.data().size() == f_model.data().size()
          if(scale_ml is None):
             if(self.alpha_beta_params is not None):
                if(self.alpha_beta_params.method == "calc"):
                   if(self.alpha_beta_params.fix_scale_for_calc_option is None):
                      scale_ml = self.scale_ml()
                   else:
                      scale_ml=self.alpha_beta_params.fix_scale_for_calc_option
                else:
                   scale_ml = 1.0
             else:
                scale_ml = 1.0
          return self.target_functor_t(f_model,
                                       alpha.data(),
                                       beta.data(),
                                       scale_ml,
                                       compute_gradients)
       if(self.target_name.count("ls") == 1):
          alpha is None and beta is None
          return self.target_functor_t(f_model, compute_gradients)

  def target_w(self, alpha=None, beta=None):
    return self.xray_target_functor_result(compute_gradients = False,
                                           alpha             = alpha,
                                           beta              = beta,
                                           scale_ml          = None,
                                           flag              = "work").target()

  def target_t(self, alpha=None, beta=None):
    return self.xray_target_functor_result(compute_gradients = False,
                                           alpha             = alpha,
                                           beta              = beta,
                                           scale_ml          = None,
                                           flag              = "test").target()

  def gradient_wrt_xyz(self, selection = None):
    structure_factor_gradients = cctbx.xray.structure_factors.gradients(
                                                miller_set    = self.f_obs_w(),
                                                cos_sin_table = True)
    gradient_flags = cctbx.xray.structure_factors.gradient_flags(site  = True,
                                                                 u_iso = False)

    if(self.target_name.count("ls") == 0):
       alpha_w, beta_w = self.alpha_beta_w()
    else:
       alpha_w, beta_w = None, None
    xrtfr = self.xray_target_functor_result(compute_gradients = True,
                                              alpha             = alpha_w,
                                              beta              = beta_w,
                                              scale_ml          = None,
                                              flag              = "work")
    if(selection is None):
       xrs = self.xray_structure
    else:
       xrs = self.xray_structure.select(selection)
    sf = structure_factor_gradients(
         mean_displacements = None,
         d_target_d_f_calc  = xrtfr.derivatives(),
         xray_structure     = xrs,
         gradient_flags     = gradient_flags,
         n_parameters       = xrs.n_parameters(gradient_flags),
         miller_set         = self.f_obs_w(),
         algorithm          = self.sf_algorithm)
    grad_xray = flex.vec3_double(sf.packed())
    return grad_xray

  def gradient_wrt_uiso(self, sqrt_u_iso):
    structure_factor_gradients = cctbx.xray.structure_factors.gradients(
                                                miller_set    = self.f_obs_w(),
                                                cos_sin_table = True)
    gradient_flags = cctbx.xray.structure_factors.gradient_flags(site  = False,
                                                                 u_iso = True)
    mean_displacements = None
    if(gradient_flags.u_iso):
       gradient_flags.sqrt_u_iso = sqrt_u_iso
       if(gradient_flags.sqrt_u_iso):
          mean_displacements = self.xray_structure.scatterers().extract_u_iso()
          if(not mean_displacements.all_ge(0)):
             raise RuntimeError(
               "Handling of anisotropic scatterers not implemented.")
          mean_displacements = flex.sqrt(mean_displacements)
    alpha_w, beta_w = self.alpha_beta_w()
    xrtfr = self.xray_target_functor_result(compute_gradients = True,
                                              alpha             = alpha_w,
                                              beta              = beta_w,
                                              scale_ml          = None,
                                              flag              = "work")
    sf = structure_factor_gradients(
         mean_displacements = mean_displacements,
         d_target_d_f_calc  = xrtfr.derivatives(),
         xray_structure     = self.xray_structure,
         gradient_flags     = gradient_flags,
         n_parameters       = self.xray_structure.n_parameters(gradient_flags),
         miller_set         = self.f_obs_w(),
         algorithm          = self.sf_algorithm)
    grad_xray = sf.packed()
    return grad_xray

  def update(self, f_calc              = None,
                   f_obs               = None,
                   f_mask              = None,
                   f_ordered_solvent   = None,
                   r_free_flags        = None,
                   u_aniso             = None,
                   k_sol               = None,
                   b_sol               = None,
                   sf_algorithm        = None,
                   target_name         = None,
                   abcd                = None,
                   alpha_beta_params   = None,
                   xray_structure      = None,
                   mask_params         = None):
    if(f_calc is not None):
       assert f_calc.data().size() == self.f_calc.data().size()
       self.f_calc = f_calc
    if(xray_structure is not None):
       self.xray_structure = xray_structure
    if(mask_params is not None):
       self.mask_params = mask_params
    if(f_obs is not None):
       assert f_obs.data().size() == self.f_obs.data().size()
       self.f_obs = f_obs
    if(f_mask is not None):
      assert f_mask.data().size() == self.f_mask.data().size()
      self.f_mask = f_mask
    if(f_ordered_solvent is not None):
       if(self.f_ordered_solvent is not None):
          assert f_ordered_solvent.data().size() == self.f_ordered_solvent.data().size()
       self.f_ordered_solvent = f_ordered_solvent
    if(r_free_flags is not None):
      assert r_free_flags.indices().size() == self.f_obs.indices().size()
      self.r_free_flags = r_free_flags
    if(u_aniso is not None):
      try: assert u_aniso.size() == 6
      except: assert len(u_aniso) == 6
      self.u_aniso = u_aniso
    if(k_sol is not None):       self.k_sol = k_sol
    if(b_sol is not None):       self.b_sol = b_sol
    if(sf_algorithm is not None):
      assert sf_algorithm in ("fft", "direct")
      self.sf_algorithm = sf_algorithm
    if(target_name is not None):
      assert target_name in self.target_names
      self.target_name = target_name
      self.setup_target_functors()
    if(abcd is not None):
      self.abcd = abcd
    if(alpha_beta_params is not None):
      self.alpha_beta_params = alpha_beta_params
    return self


  def f_ordered_solvent_w(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.f_ordered_solvent.select(~self.r_free_flags.data())
    else:
      return self.f_ordered_solvent

  def f_bulk(self):
    ss = 1./flex.pow2(self.f_calc.d_spacings().data()) / 4.
    data = self.f_mask.data() * flex.exp(-ss * self.b_sol) * self.k_sol
    return miller.array(miller_set = self.f_calc, data = data)

  def f_bulk_w(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.f_bulk().select(~self.r_free_flags.data())
    else:
      return self.f_bulk()

  def f_bulk_t(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.f_bulk().select(self.r_free_flags.data())
    else:
      return self.f_bulk()

  def fu_aniso(self):
    return bulk_solvent.fu_aniso(self.u_aniso,
                                 self.f_calc.indices(),
                                 self.f_calc.unit_cell())

  def fu_aniso_w(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.fu_aniso().select(~self.r_free_flags.data())
    else:
      return self.fu_aniso()

  def fu_aniso_t(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.fu_aniso().select(self.r_free_flags.data())
    else:
      return self.fu_aniso()

  def f_model(self):
    fu_aniso = self.fu_aniso()
    if(self.f_ordered_solvent is None):
       data = fu_aniso * (self.f_calc.data() + self.f_bulk().data())
    else:
       data = fu_aniso * (self.f_calc.data() + self.f_bulk().data() + \
                          self.f_ordered_solvent.data())
    return miller.array(miller_set = self.f_calc, data = data)

  def f_model_scaled_with_k1(self):
    return miller.array(miller_set = self.f_calc,
                        data       = self.scale_k1()*self.f_model().data())

  def f_model_scaled_with_k1_t(self):
    return miller.array(miller_set = self.f_calc_t(),
                        data       = self.scale_k1_t()*self.f_model_t().data())

  def f_model_scaled_with_k1_w(self):
    return miller.array(miller_set = self.f_calc_w(),
                        data       = self.scale_k1_w()*self.f_model_w().data())

  def f_model_w(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.f_model().select(~self.r_free_flags.data())
    else:
      return self.f_model()

  def f_model_t(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.f_model().select(self.r_free_flags.data())
    else:
      return self.f_model()

  def f_star_w_star_obj(self):
    #XXX why I use self.f_calc and not f_model ????????????????????????????????
    alpha, beta = self.alpha_beta()
    obj = max_lik.f_star_w_star_mu_nu(
                                 f_obs          = self.f_obs.data(),
                                 f_model        = flex.abs(self.f_calc.data()),
                                 alpha          = alpha.data(),
                                 beta           = beta.data(),
                                 space_group    = self.f_obs.space_group(),
                                 miller_indices = self.f_obs.indices())
    return obj

  def f_star_w_star(self):
    obj = self.f_star_w_star_obj()
    f_star = miller.array(miller_set = self.f_calc,
                          data       = obj.f_star())
    w_star = miller.array(miller_set = self.f_calc,
                          data       = obj.w_star())
    return f_star, w_star

  def f_star_w_star_work(self):
    assert self.r_free_flags is not None
    f_star, w_star = self.f_star_w_star()
    flags = self.r_free_flags.data()
    if(flags.count(True) > 0):
       return f_star.select(~flags), w_star.select(~flags)
    else:
       return f_star, w_star

  def f_star_w_star_test(self):
    assert self.r_free_flags is not None
    f_star, w_star = self.f_star_w_star()
    flags = self.r_free_flags.data()
    if(flags.count(True) > 0):
       return f_star.select(flags), w_star.select(flags)
    else:
       return f_star, w_star

  def u_iso(self):
    return (self.u_aniso[0]+self.u_aniso[1]+self.u_aniso[2])/3.0

  def u_iso_as_u_aniso(self):
    ui = self.u_iso()
    return [ui,ui,ui,0.0,0.0,0.0]

  def r_work_in_lowest_resolution_bin(self, reflections_per_bin=200):
    fo_w = self.f_obs_w()
    fc_w = self.f_model_w()
    if(fo_w.data().size() > reflections_per_bin):
       fo_w.setup_binner(reflections_per_bin = reflections_per_bin)
    else:
       fo_w.setup_binner(reflections_per_bin = fo_w.data().size())
    fo_w.use_binning_of(fo_w)
    fc_w.use_binning_of(fo_w)
    r = []
    for i_bin in fo_w.binner().range_used():
        sel_w = fo_w.binner().selection(i_bin)
        sel_fo_w = fo_w.select(sel_w)
        sel_fc_w = fc_w.select(sel_w)
        r.append(bulk_solvent.r_factor(sel_fo_w.data(), sel_fc_w.data()))
    return r[0]

  def f_mask_w(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.f_mask.select(~self.r_free_flags.data())
    else:
      return self.f_mask

  def f_mask_t(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.f_mask.select(self.r_free_flags.data())
    else:
      return self.f_mask

  def f_calc_w(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.f_calc.select(~self.r_free_flags.data())
    else:
      return self.f_calc

  def f_calc_t(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.f_calc.select(self.r_free_flags.data())
    else:
      return self.f_calc

  def f_obs_w(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.f_obs.select(~self.r_free_flags.data())
    else:
      return self.f_obs

  def f_obs_t(self):
    assert self.r_free_flags is not None
    if(self.r_free_flags.data().count(True) > 0):
      return self.f_obs.select(self.r_free_flags.data())
    else:
      return self.f_obs

  def k_sol_b_sol(self):
    return self.k_sol, self.b_sol

  def k_sol(self):
    return self.k_sol

  def b_sol(self):
    return self.b_sol

  def alpha_beta(self):
    alpha, beta = None, None
    ab_params = self.alpha_beta_params
    if(self.alpha_beta_params is not None):
       assert self.alpha_beta_params.method in ("est", "calc")
       if(self.alpha_beta_params.method == "est"):
          alpha, beta = maxlik.alpha_beta_est_manager(
           f_obs           = self.f_obs,
           f_calc          = self.f_model(),
           test_ref_in_bin = self.alpha_beta_params.test_ref_in_bin,
           flags           = self.r_free_flags.data(),
           interpolation   = self.alpha_beta_params.interpolation).alpha_beta()
       if(self.alpha_beta_params.method == "calc"):
         check = flex.max(flex.abs(self.f_ordered_solvent_dist.data()))
         if(check < 1.e-9):
            n_atoms_missed = ab_params.number_of_macromolecule_atoms_absent + \
                             ab_params.number_of_waters_absent
            alpha, beta = maxlik.alpha_beta_calc(
                    f                = self.f_obs,
                    n_atoms_absent   = n_atoms_missed,
                    n_atoms_included = ab_params.n_atoms_included,
                    bf_atoms_absent  = ab_params.bf_atoms_absent,
                    final_error      = ab_params.final_error,
                    absent_atom_type = ab_params.absent_atom_type).alpha_beta()
         else:
            alpha, beta = max_like_non_uniform.alpha_beta(
                  f_dist                   = self.f_ordered_solvent_dist,
                  n_atoms_included         = ab_params.n_atoms_included,
                  n_nonwater_atoms_absent  = ab_params.number_of_macromolecule_atoms_absent,
                  n_water_atoms_absent     = ab_params.number_of_waters_absent,
                  bf_atoms_absent          = ab_params.bf_atoms_absent,
                  final_error              = ab_params.final_error,
                  absent_atom_type         = ab_params.absent_atom_type)
    else:
       alpha, beta = maxlik.alpha_beta_est_manager(
                                    f_obs           = self.f_obs,
                                    f_calc          = self.f_model(),
                                    test_ref_in_bin = 200,
                                    flags           = self.r_free_flags.data(),
                                    interpolation   = False).alpha_beta()
    return alpha, beta

  def alpha_beta_w(self):
    assert self.r_free_flags is not None
    alpha, beta = self.alpha_beta()
    if(self.r_free_flags.data().count(True) > 0):
      return alpha.select(~self.r_free_flags.data()), \
             beta.select(~self.r_free_flags.data())
    else:
      return alpha, beta

  def alpha_beta_t(self):
    assert self.r_free_flags is not None
    alpha, beta = self.alpha_beta()
    if(self.r_free_flags.data().count(True) > 0):
      return alpha.select(self.r_free_flags.data()), \
             beta.select(self.r_free_flags.data())
    else:
      return alpha, beta

  def targets_w(self, alpha=None, beta=None):
  #XXX works only for MLHL target !!!
    assert self.target_functors is not None
    assert self.target_functors.target_name == self.target_name
    ftor = self.target_functor_w
    if(self.target_name.count("ls") == 1):
      return ftor(self.f_model_w(), False).target()
    if(self.target_name in ("ml","mlhl")):
      if(alpha is None and beta is None):
         alpha, beta = self.alpha_beta_w()
      if(self.alpha_beta_params is not None):
         if(self.alpha_beta_params.method == "calc"):
            if(self.alpha_beta_params.fix_scale_for_calc_option == None):
               ml_scale = self.scale_ml()
            else:
               ml_scale = self.alpha_beta_params.fix_scale_for_calc_option
         else:
            ml_scale = 1.0
      else:
         ml_scale = 1.0
      dummy = self.f_obs_w().deep_copy()
      return dummy.array(data = ftor(self.f_model_w(),
                                     alpha.data(),
                                     beta.data(),
                                     ml_scale,
                                     False).targets())

  def derivatives_w(self, alpha=None, beta=None):
    assert self.target_functors is not None
    assert self.target_functors.target_name == self.target_name
    ftor = self.target_functor_w
    if(self.target_name.count("ls") == 1):
      return ftor(self.f_model_w(), False).target()
    if(self.target_name in ("ml","mlhl")):
      if(alpha is None and beta is None):
         alpha, beta = self.alpha_beta_w()
      if(self.alpha_beta_params is not None):
         if(self.alpha_beta_params.method == "calc"):
            if(self.alpha_beta_params.fix_scale_for_calc_option == None):
               ml_scale = self.scale_ml()
            else:
               ml_scale = self.alpha_beta_params.fix_scale_for_calc_option
         else:
            ml_scale = 1.0
      else:
         ml_scale = 1.0
      dummy = self.f_obs_w().deep_copy()
      return dummy.array(data = ftor(self.f_model_w(),
                                     alpha.data(),
                                     beta.data(),
                                     ml_scale,
                                     True).derivatives())

  def r_work(self):
    fo = self.f_obs_w().data()
    fc = self.f_model_w().data()
    return bulk_solvent.r_factor(fo,fc)

  def r_free(self):
    return bulk_solvent.r_factor(self.f_obs_t().data(),
                                 self.f_model_t().data())

  def scale_k1(self):
    fo = self.f_obs.data()
    fc = flex.abs(self.f_model().data())
    return flex.sum(fo*fc) / flex.sum(fc*fc)

  def scale_k1_w(self):
    fo = self.f_obs_w().data()
    fc = flex.abs(self.f_model_w().data())
    return flex.sum(fo*fc) / flex.sum(fc*fc)

  def scale_k1_t(self):
    fo = self.f_obs_t().data()
    fc = flex.abs(self.f_model_t().data())
    return flex.sum(fo*fc) / flex.sum(fc*fc)

  def scale_k2_w(self):
    fo = self.f_obs_w().data()
    fc = flex.abs(self.f_model_w().data())
    return flex.sum(fo*fc) / flex.sum(fo*fo)

  def scale_k2_t(self):
    fo = self.f_obs_t().data()
    fc = flex.abs(self.f_model_t().data())
    return flex.sum(fo*fc) / flex.sum(fo*fo)

  def scale_k3_w(self):
    eps = self.f_obs_w().epsilons().data().as_double()
    mul = self.f_obs_w().multiplicities().data().as_double()
    fo = self.f_obs_w().data()
    fc = flex.abs(self.f_model_w().data())
    return math.sqrt(flex.sum(fo * fo * mul / eps) / \
                     flex.sum(fc * fc * mul / eps) )

  def scale_k3_t(self):
    eps = self.f_obs_t().epsilons().data().as_double()
    mul = self.f_obs_t().multiplicities().data().as_double()
    fo = self.f_obs_t().data()
    fc = flex.abs(self.f_model_t().data())
    return math.sqrt(flex.sum(fo * fo * mul / eps) / \
                     flex.sum(fc * fc * mul / eps) )

  def scale_k1_low_high(self, d = 6.0):
    fo_l = self.f_obs.resolution_filter(d_min = 6.0, d_max = 999.9).data()
    fo_h = self.f_obs.resolution_filter(d_min = 0.0, d_max = 6.0).data()
    fm_l = flex.abs(self.f_model().resolution_filter(d_min = 6.0, d_max = 999.9).data())
    fm_h = flex.abs(self.f_model().resolution_filter(d_min = 0.0, d_max = 6.0).data())
    scale_l = flex.sum(fo_l*fm_l) / flex.sum(fm_l*fm_l)
    scale_h = flex.sum(fo_h*fm_h) / flex.sum(fm_h*fm_h)
    return scale_l, scale_h

  def scale_ml(self):
    assert self.alpha_beta_params.method == "calc"
    alpha, beta = self.alpha_beta_w()
    scale_manager = bss.uaniso_ksol_bsol_scaling_minimizer(
               self.f_calc_w(),
               self.f_obs_w(),
               self.f_mask_w(),
               k_initial = 0.,
               b_initial = 0.,
               u_initial = [0,0,0,0,0,0],
               scale_initial = self.scale_k3_w(),
               refine_k = False,
               refine_b = False,
               refine_u = False,
               refine_scale = True,
               alpha = alpha.data(),
               beta = beta.data(),
               lbfgs_exception_handling_params = lbfgs.exception_handling_parameters(
                         ignore_line_search_failed_step_at_lower_bound = True,
                         ignore_line_search_failed_step_at_upper_bound = True,
                         ignore_line_search_failed_maxfev              = True))
    return scale_manager.scale_min

  def figures_of_merit(self):
    alpha, beta = self.alpha_beta()
    data = abs(self.f_model()).data()
    return max_lik.fom_and_phase_error(
                                   f_obs          = self.f_obs.data(),
                                   f_model        = data,
                                   alpha          = alpha.data(),
                                   beta           = beta.data(),
                                   space_group    = self.f_obs.space_group(),
                                   miller_indices = self.f_obs.indices()).fom()

  def phase_errors(self):
    alpha, beta = self.alpha_beta()
    data = abs(self.f_model()).data()
    return max_lik.fom_and_phase_error(
                           f_obs          = self.f_obs.data(),
                           f_model        = data,
                           alpha          = alpha.data(),
                           beta           = beta.data(),
                           space_group    = self.f_obs.space_group(),
                           miller_indices = self.f_obs.indices()).phase_error()

  def phase_errors_test(self):
    assert self.r_free_flags is not None
    pher = self.phase_errors()
    if(self.r_free_flags.data().count(True) > 0):
      return pher.select(self.r_free_flags.data())
    else:
      return pher


  def phase_errors_work(self):
    assert self.r_free_flags is not None
    pher = self.phase_errors()
    if(self.r_free_flags.data().count(True) > 0):
      return pher.select(~self.r_free_flags.data())
    else:
      return pher

  def phase_errors_test(self):
    assert self.r_free_flags is not None
    pher = self.phase_errors()
    if(self.r_free_flags.data().count(True) > 0):
      return pher.select(self.r_free_flags.data())
    else:
      return pher

  def map_coefficients(self,
                       map_type          = "k*Fobs-n*Fmodel",
                       k                 = 1,
                       n                 = 1,
                       w1                = None,
                       w2                = None):
    assert map_type in ("k*Fobs-n*Fmodel",
                        "2m*Fobs-D*Fmodel",
                        "m*Fobs-D*Fmodel",
                        "k*w1*Fobs-n*w2*Fmodel")
    if(map_type == "k*Fobs-n*Fmodel"):
       d_obs = miller.array(miller_set = self.f_calc,
                            data       = self.f_obs.data()*k
                           ).phase_transfer(phase_source = self.f_calc)
       d_model = self.f_model_scaled_with_k1().data()*n
       return miller.array(miller_set = self.f_calc,
                           data       = d_obs.data() - d_model)
    if(map_type == "2m*Fobs-D*Fmodel"):
      alpha, beta = self.alpha_beta()
      d_obs = miller.array(miller_set = self.f_calc,
                           data       = self.f_obs.data()*2.*self.figures_of_merit()
                          ).phase_transfer(phase_source = self.f_calc)
      d_model = self.f_model().data()*alpha.data()
      return miller.array(miller_set = self.f_calc,
                          data       = d_obs.data() - d_model)
    if(map_type == "m*Fobs-D*Fmodel"):
      alpha, beta = self.alpha_beta()
      d_obs = miller.array(miller_set = self.f_calc,
                           data       = self.f_obs.data()*self.figures_of_merit()
                          ).phase_transfer(phase_source = self.f_calc)
      d_model = self.f_model().data()*alpha.data()
      ####
      #result = miller.array(miller_set = self.f_calc,
      #                      data       = d_obs.data() - d_model)
      #centrics  = result.select_centric()
      #acentrics = result.select_acentric()
      #acentrics_data = acentrics.data() * 2.0
      #centrics_data  = centrics.data()
      #new = acentrics.customized_copy(
      #          indices = acentrics.indices().concatenate(centrics.indices()),
      #          data    = acentrics_data.concatenate(centrics_data) )
      ####
      #return new
      #f = open("qq","w")
      #fom = self.figures_of_merit()
      #for i, a, b in zip(self.f_calc.indices(), fom, alpha.data()):
      #    print >> f, "%5d%5d%5d %10.3f %10.3f" % (i[0], i[1], i[2], a, b)
      return miller.array(miller_set = self.f_calc,
                          data       = d_obs.data() - d_model)
    if(map_type == "k*w1*Fobs-n*w2*Fmodel"):
      raise RuntimeError("Not implemented.")

  def electron_density_map(self,
                           map_type          = "k*Fobs-n*Fmodel",
                           k                 = 1,
                           n                 = 1,
                           w1                = None,
                           w2                = None,
                           resolution_factor = 1/3.,
                           symmetry_flags = None):
    assert map_type in ("k*Fobs-n*Fmodel",
                        "2m*Fobs-D*Fmodel",
                        "m*Fobs-D*Fmodel",
                        "m*w1*Fobs-n*w2*Fmodel")
    return self.map_coefficients(
                       map_type          = map_type,
                       k                 = k,
                       n                 = n,
                       w1                = w1,
                       w2                = w2).fft_map(
                                         resolution_factor = resolution_factor,
                                         symmetry_flags    = symmetry_flags)

  def show(self, out=None):
    if(out is None): log = self.log
    else: log = out
    print >> log, "f_calc          = ", self.f_calc
    print >> log, "f_obs           = ", self.f_obs
    print >> log, "f_mask          = ", self.f_mask
    print >> log, "r_free_flags    = ", self.r_free_flags
    print >> log, "u_aniso         = ", self.u_aniso
    print >> log, "k_sol           = ", self.k_sol
    print >> log, "b_sol           = ", self.b_sol
    print >> log, "sf_algorithm    = ", self.sf_algorithm
    print >> log, "target_name     = ", self.target_name
    log.flush()

  def show_k_sol_b_sol_u_aniso_target(self, header = None, target = None):
    log = self.log
    p = " "
    if(header is None): header = ""
    line_len = len("|-"+"|"+header)
    fill_len = 80-line_len-1
    print >> log, "|-"+header+"-"*(fill_len)+"|"
    k_sol = self.k_sol
    b_sol = self.b_sol
    u0,u1,u2,u3,u4,u5 = self.u_aniso
    if(target is None):
       target_w = self.target_w()
    else:
       target_w = target
    alpha, beta = self.alpha_beta_w()
    alpha_d = alpha.data()
    a_mean = flex.mean(alpha_d)
    a_zero = (alpha_d <= 0.0).count(True)
    r_work = self.r_work()
    u_isos = self.xray_structure.extract_u_iso_or_u_equiv()
    b_iso_mean = flex.mean(u_isos * math.pi**2*8)
    print >> log, "| k_sol=%5.2f b_sol=%7.2f target_w =%20.6f r_work=%7.4f" % \
                  (k_sol, b_sol, target_w, r_work) + 5*p+"|"
    print >> log, "| B(11,22,33,12,13,23)=%9.4f%9.4f%9.4f%9.4f%9.4f%9.4f |" % \
                  (u0,u1,u2,u3,u4,u5)
    print >> log, "| n_ordered_solv=%6d b_ordered_solv=%7.2f b_mean=%7.2f " \
                  "n_atoms=%7d |" % (self.n_ordered_water,\
                                 self.b_ordered_water,b_iso_mean,u_isos.size())
    print >> log, "| mean alpha:%8.4f  number of alpha <= 0.0:%7d" % \
                  (a_mean, a_zero)+25*p+"|"
    print >> log, "|"+"-"*77+"|"
    log.flush()

  def show_essential(self, header = None):
    log = self.log
    p = " "
    if(header is None): header = ""
    line_len = len("|-"+"|"+header)
    fill_len = 80-line_len-1
    print >> log, "|-"+header+"-"*(fill_len)+"|"
    r_work = self.r_work()
    r_test = self.r_free()
    scale_work = self.scale_k1_w()
    scale_test = self.scale_k1_t()
    k_sol = self.k_sol
    b_sol = self.b_sol
    u0,u1,u2,u3,u4,u5 = self.u_aniso
    u_iso = self.u_iso()
    try:    target_work = "%13.6E" % self.target_w()
    except: target_work = str(None)
    try:    target_test = "%13.6E" % self.target_t()
    except: target_test = str(None)
    print >> log, "| r-factor (work) = %6.4f  scale (work) = %7.4f" \
          "  ksol= %5.2f  bsol= %6.2f |" % (r_work, scale_work, k_sol,b_sol)
    print >> log, "| r-factor (free) = %6.4f  scale (free) = %7.4f" % (
            r_test, scale_test) +p*28+"|"
    print >> log, "| anisotropic scale matrix (Cartesian basis): " \
        + "| xray targets:"+17*p+"|"
    print >> log, "|  B11= %8.3f B12= %8.3f B13= %8.3f  |" % \
      (u0,u3,u4), "target name = %11s"%self.target_name+5*p+"|"
    print >> log, "|"+16*p+"B22= %8.3f B23= %8.3f  | " % (u1,u5) \
        + "target (work) = %13s"%target_work+" |"
    print >> log, "|"+30*p+"B33= %8.3f  | "% (u2)+"target (free) = %13s"% \
          target_test+" |"
    print >> log, "| (B11+B22+B33)/3 = %8.3f"%u_iso+18*p+"|"+31*p+"|"
    print >> log, "|"+"-"*77+"|"
    #if (not_approx_equal(self.u_aniso,
    #                     self.f_obs.average_b_cart(self.u_aniso))):
    #  raise RuntimeError(
    #    "Internal error: Corrupt anisotropic scale matrix:\n  %s\n  %s" %
    #      (str(self.u_aniso), str(b_cart_ave)))
    log.flush()

  def show_comprehensive(self, header = "",
                               reflections_per_bin = 200,
                               max_number_of_bins  = 30):
    log = self.log
    self.show_essential(header = header)
    print >> log
    self.statistics_in_resolution_bins(
                                     reflections_per_bin = reflections_per_bin,
                                     max_number_of_bins  = max_number_of_bins)
    print >> log
    self.show_fom_phase_error_alpha_beta_in_bins(
                                     reflections_per_bin = reflections_per_bin,
                                     max_number_of_bins  = max_number_of_bins)

  def statistics_in_resolution_bins(self, reflections_per_bin = 200,
                                          max_number_of_bins  = 30):
    statistics_in_resolution_bins(
      fmodel          = self,
      target_functors = self.target_functors,
      reflections_per_bin = reflections_per_bin,
      max_number_of_bins  = max_number_of_bins,
      out=self.log)

  def r_factors_in_resolution_bins(self, reflections_per_bin = 200,
                                          max_number_of_bins  = 30):
    r_factors_in_resolution_bins(
      fmodel              = self,
      reflections_per_bin = reflections_per_bin,
      max_number_of_bins  = max_number_of_bins,
      out=self.log)

  def show_fom_phase_error_alpha_beta_in_bins(self, reflections_per_bin = 200,
                                                    max_number_of_bins  = 30):
    show_fom_phase_error_alpha_beta_in_bins(
      fmodel              = self,
      reflections_per_bin = reflections_per_bin,
      max_number_of_bins  = max_number_of_bins,
      out=self.log)

def statistics_in_resolution_bins(fmodel,
                                  target_functors,
                                  reflections_per_bin,
                                  max_number_of_bins,
                                  out):
  d_max,d_min = fmodel.f_obs.d_max_min()
  fo_t = fmodel.f_obs_t()
  fc_t = fmodel.f_model_t()
  fo_w = fmodel.f_obs_w()
  fc_w = fmodel.f_model_w()
  alpha_w, beta_w = fmodel.alpha_beta_w()
  alpha_t, beta_t = fmodel.alpha_beta_t()
  if(fo_t.data().size() > reflections_per_bin):
    fo_t.setup_binner(reflections_per_bin = reflections_per_bin,
                      d_max = d_max, d_min = d_min)
  else:
    fo_t.setup_binner(reflections_per_bin = fo_t.data().size(),
                      d_max = d_max, d_min = d_min)
  if(len(fo_t.binner().range_used()) > max_number_of_bins):
    fo_t.setup_binner(n_bins = max_number_of_bins,
                      d_max = d_max, d_min = d_min)
  fc_t.use_binning_of(fo_t)
  fo_w.use_binning_of(fo_t)
  fc_w.use_binning_of(fo_t)
  alpha_w.use_binning_of(fo_t)
  alpha_t.use_binning_of(fo_t)
  beta_w.use_binning_of(fo_t)
  beta_t.use_binning_of(fo_t)
  print >> out, "|"+"-"*77+"|"
  print >> out, "| Bin     Resolution       No. Refl.    " \
                  "R-factors              Targets        |"
  print >> out, "|number     range         work   test   " \
                  "work   test          work         test|"
  for i_bin in fo_t.binner().range_used():
    sel_t = fo_t.binner().selection(i_bin)
    sel_w = fo_w.binner().selection(i_bin)
    sel_fo_t = fo_t.select(sel_t)
    sel_fc_t = fc_t.select(sel_t)
    sel_fo_w = fo_w.select(sel_w)
    sel_fc_w = fc_w.select(sel_w)
    sel_alpha_t = alpha_t.select(sel_t)
    sel_beta_t  = beta_t.select(sel_t)
    sel_alpha_w = alpha_w.select(sel_w)
    sel_beta_w  = beta_w.select(sel_w)
    xray_target_functor_w = target_functors.target_functor_w(selection = sel_w)
    xray_target_functor_t = target_functors.target_functor_t(selection = sel_t)
    if(fmodel.target_name.count("ls") == 1):
      target_w = xray_target_functor_w(sel_fc_w, False).target()
      target_t = xray_target_functor_t(sel_fc_t, False).target()
    elif(fmodel.target_name == "ml" or fmodel.target_name == "mlhl"):
      target_w = xray_target_functor_w(sel_fc_w,
                                       sel_alpha_w.data(),
                                       sel_beta_w.data(),
                                       1.0,
                                       False).target()
      target_t = xray_target_functor_t(sel_fc_t,
                                       sel_alpha_t.data(),
                                       sel_beta_t.data(),
                                       1.0,
                                       False).target()
    r_w = bulk_solvent.r_factor(sel_fo_w.data(), sel_fc_w.data())
    r_t = bulk_solvent.r_factor(sel_fo_t.data(), sel_fc_t.data())
    nt = sel_fo_t.data().size()
    nw = sel_fo_w.data().size()
    d_range = fo_t.binner().bin_legend(
      i_bin=i_bin, show_bin_number=False, show_counts=False)
    print >> out, "|%3d: %s %6d %6d %6.4f %6.4f  %12.5E %12.5E|" % (
      i_bin, d_range, nw, nt, r_w, r_t, target_w, target_t)
  print >> out, "|"+"-"*77+"|"
  out.flush()

def r_factors_in_resolution_bins(fmodel,
                                 reflections_per_bin,
                                 max_number_of_bins,
                                 out):
  d_max,d_min = fmodel.f_obs.d_max_min()
  fo_t = fmodel.f_obs_t()
  fc_t = fmodel.f_model_t()
  fo_w = fmodel.f_obs_w()
  fc_w = fmodel.f_model_w()
  if(fo_t.data().size() > reflections_per_bin):
    fo_t.setup_binner(reflections_per_bin = reflections_per_bin,
                      d_max = d_max, d_min = d_min)
  else:
    fo_t.setup_binner(reflections_per_bin = fo_t.data().size(),
                      d_max = d_max, d_min = d_min)
  if(len(fo_t.binner().range_used()) > max_number_of_bins):
    fo_t.setup_binner(n_bins = max_number_of_bins,
                      d_max = d_max, d_min = d_min)
  fo_w.use_binning_of(fo_t)
  fc_t.use_binning_of(fo_t)
  fc_w.use_binning_of(fo_t)
  print >> out, " Bin     Resolution       No. Refl.      R-factors      "
  print >> out, "number     range         work   test     work   test    "
  for i_bin in fo_t.binner().range_used():
    sel_t = fo_t.binner().selection(i_bin)
    sel_w = fo_w.binner().selection(i_bin)
    sel_fo_t = fo_t.select(sel_t)
    sel_fc_t = fc_t.select(sel_t)
    sel_fo_w = fo_w.select(sel_w)
    sel_fc_w = fc_w.select(sel_w)
    r_w = bulk_solvent.r_factor(sel_fo_w.data(), sel_fc_w.data())
    r_t = bulk_solvent.r_factor(sel_fo_t.data(), sel_fc_t.data())
    nt = sel_fo_t.data().size()
    nw = sel_fo_w.data().size()
    d_range = fo_t.binner().bin_legend(
      i_bin=i_bin, show_bin_number=False, show_counts=False)
    print >> out, "%3d: %s %6d %6d   %6.4f %6.4f" % (
      i_bin, d_range, nw, nt, r_w, r_t)
  out.flush()


def show_fom_phase_error_alpha_beta_in_bins(fmodel,
                                            reflections_per_bin,
                                            max_number_of_bins,
                                            out):
  d_max,d_min = fmodel.f_obs.d_max_min()
  fom = fmodel.figures_of_merit()
  phase_errors_work = fmodel.phase_errors_work()
  phase_errors_test = fmodel.phase_errors_test()
  mi_a, mi_b = fmodel.alpha_beta()
  alpha, beta = mi_a, mi_b
  mi_fom = fmodel.f_calc.array(data = fom)
  mi_per_work = fmodel.f_calc_w().array(data = phase_errors_work)
  mi_per_test = fmodel.f_calc_t().array(data = phase_errors_test)
  mi_f   = fmodel.r_free_flags
  test_set = mi_f.select(fmodel.r_free_flags.data())
  if(test_set.data().size() > reflections_per_bin):
     test_set.setup_binner(reflections_per_bin = reflections_per_bin,
                           d_max = d_max, d_min = d_min)
  else:
     test_set.setup_binner(reflections_per_bin = test_set.data().size(),
                           d_max = d_max, d_min = d_min)
  if(len(test_set.binner().range_used()) > max_number_of_bins):
     test_set.setup_binner(n_bins = max_number_of_bins,
                           d_max = d_max, d_min = d_min)
  mi_per_test.use_binning_of(test_set)
  mi_per_work.use_binning_of(test_set)
  mi_fom.use_binning_of(test_set)
  mi_a.use_binning_of(test_set)
  mi_b.use_binning_of(test_set)
  mi_f.use_binning_of(test_set)
  print >> out, "|"+"-"*77+"|"
  print >> out, "|R-free likelihood based estimates for figures of merit," \
                  " absolute phase error,|"
  print >> out, "|and distribution parameters alpha and beta" \
                  " (Acta Cryst. (1995). A51, 880-887)|"
  print >> out, "|"+" "*77+"|"
  print >> out, "| Bin     Resolution      No. Refl.   FOM   Phase error    "\
                " Alpha        Beta |"
  print >> out, "|  #        range        work  test        work      test  "\
                "                   |"
  for i_bin in test_set.binner().range_used():
    sel = mi_fom.binner().selection(i_bin)
    sel_work = mi_per_work.binner().selection(i_bin)
    sel_test = mi_per_test.binner().selection(i_bin)
    sel_mi_fom = mi_fom.select(sel)
    sel_mi_per_work = mi_per_work.select(sel_work)
    sel_mi_per_test = mi_per_test.select(sel_test)
    sel_mi_a   = mi_a.select(sel)
    sel_mi_b   = mi_b.select(sel)
    sel_mi_f   = mi_f.select(sel)
    sel_mi_fom_ave = flex.mean(sel_mi_fom.data())
    sel_mi_per_work_data = sel_mi_per_work.data()
    sel_mi_per_test_data = sel_mi_per_test.data()
    assert sel_mi_per_work_data.size() >= sel_mi_per_test_data.size()
    sel_mi_per_work_ave = flex.mean(sel_mi_per_work_data)
    sel_mi_per_test_ave = flex.mean(sel_mi_per_test_data)
    sel_mi_a_ave   = flex.mean(sel_mi_a.data())
    sel_mi_b_ave   = flex.mean(sel_mi_b.data())
    nt = sel_mi_f.data().count(True)
    nw = sel_mi_f.data().count(False)
    assert nt+nw == sel_mi_b.data().size()
    d_range = mi_fom.binner().bin_legend(i_bin=i_bin, show_bin_number=False,\
                                         show_counts=False)
    print >> out, "|%3d: %s%6d%6d%6.3f%8.3f%8.3f%8.3f%12.3f |" % (
      i_bin,d_range,nw,nt,sel_mi_fom_ave,sel_mi_per_work_ave,\
      sel_mi_per_test_ave,sel_mi_a_ave,sel_mi_b_ave)
  alpha_min  = flex.min(alpha.data())
  beta_min   = flex.min(beta.data())
  alpha_max  = flex.max(alpha.data())
  beta_max   = flex.max(beta.data())
  alpha_mean = flex.mean(alpha.data())
  beta_mean  = flex.mean(beta.data())
  fom_min    = flex.min(fom)
  fom_max    = flex.max(fom)
  fom_mean   = flex.mean(fom)
  per_min_work    = flex.min(phase_errors_work)
  per_max_work    = flex.max(phase_errors_work)
  per_mean_work   = flex.mean(phase_errors_work)
  per_min_test    = flex.min(phase_errors_test)
  per_max_test    = flex.max(phase_errors_test)
  per_mean_test   = flex.mean(phase_errors_test)
  print >> out, \
    "|alpha:            min = %12.4f max = %12.4f mean = %12.4f  |" % \
      (alpha_min, alpha_max, alpha_mean)
  print >> out, \
    "|beta:             min = %12.4f max = %12.4f mean = %12.4f  |" % \
      (beta_min, beta_max, beta_mean)
  print >> out, \
    "|figures of merit: min = %12.4f max = %12.4f mean = %12.4f  |" % \
      (fom_min, fom_max, fom_mean)
  print >> out,"|phase err.(work): min =%13.4f max =%13.4f mean =%13.4f  |" % \
      (per_min_work, per_max_work, per_mean_work)
  print >> out,"|phase err.(test): min =%13.4f max =%13.4f mean =%13.4f  |" % \
      (per_min_test, per_max_test, per_mean_test)
  if(alpha_min <= 0.0):
    print >> out, "| *** f_model warning: there are some alpha <= 0.0 ***" \
      "                        |"
    amz = alpha.data() <= 0.0
    print >> out, "|                      number of alpha <= 0.0: %6d" \
      "                         |" % (amz.count(True))
    bmz = beta.data() <= 0.0
  if(beta_min <= 0.0):
    print >> out, "| *** f_model warning: there are some beta <= 0.0 ***" \
      "                         |"
    bmz = beta.data() <= 0.0
    print >> out, "|   number of beta <= 0.0: %6d |" % (bmz.count(True))
  print >> out, "|"+"-"*77+"|"
  out.flush()

def ls_ff_weights(f_obs, atom, B):
  d_star_sq_data = f_obs.d_star_sq().data()
  table = wk1995(atom).fetch()
  ff = table.at_d_star_sq(d_star_sq_data) * flex.exp(-B/4.0*d_star_sq_data)
  weights = 1.0/flex.pow2(ff)
  return weights

def ls_sigma_weights(f_obs):
  if(f_obs.sigmas() is not None):
     sigmas_squared = flex.pow2(f_obs.sigmas())
  else:
     sigmas_squared = flex.double(f_obs.data().size(), 1.0)
  assert sigmas_squared.all_gt(0)
  weights = 1 / sigmas_squared
  return weights

def kb_range(x_max, x_min, step):
  x_range = []
  x = x_min
  while x <= x_max + 0.0001:
    x_range.append(x)
    x += step
  return x_range
