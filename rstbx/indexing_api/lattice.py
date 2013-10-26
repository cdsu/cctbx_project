from __future__ import division
from rstbx.array_family import flex
from rstbx.indexing_api import dps_extended
from rstbx.indexing_api.sampling import hemisphere_shortcut
from rstbx.dps_core import Directional_FFT
import math,cmath
from scitbx import matrix
from libtbx.test_utils import approx_equal
import boost.python

class _(boost.python.injector, dps_extended):

  def index(self,raw_spot_input=None,panel_addresses=None):
    assert raw_spot_input is not None
    self.raw_spot_input = raw_spot_input # deprecate record
    # must be x, y, phi in degrees, as a vec3_double
    self.setMaxcell(self.max_cell) # extended API

    if len(self.detector) > 1:
      assert len(raw_spot_input) == len(panel_addresses)

    self.panelID = panel_addresses
    reciprocal_space_vectors = self.raw_spot_positions_mm_to_reciprocal_space(
      self.raw_spot_input, self.detector, self.inv_wave, self.S0_vector, self.axis,
      self.panelID)

    self.setXyzData(reciprocal_space_vectors) # extended API

    hemisphere_shortcut(ai = self, # extended API
        characteristic_sampling = self.recommended_grid_sampling_rad,
        max_cell = self.max_cell
      )

  def sum_score_detail(self,reciprocal_space_vectors):
    """Evaluates the probability that the trial value of ( S0_vector | origin_offset ) is correct,
       given the current estimate and the observations.  The trial value comes through the
       reciprocal space vectors, and the current estimate comes through the short list of
       DPS solutions. Actual return value is a sum of NH terms, one for each DPS solution, each ranging
       from -1.0 to 1.0"""
    nh = min ( self.getSolutions().size(), 20) # extended API
    solutions = self.getSolutions() #extended API
    sum_score = 0.0
    for t in xrange(nh):
      #if t!=unique:continue
      dfft = Directional_FFT(angle = solutions[t], xyzdata = reciprocal_space_vectors,
                            granularity = self.granularity, amax = self.amax, # extended API
                            F0_cutoff = 11)
      kval = dfft.kval();
      kmax = dfft.kmax();
      kval_cutoff = self.raw_spot_input.size()/4.0; # deprecate record
      if ( kval > kval_cutoff ):
        ff=dfft.fft_result;
        kbeam = ((-dfft.pmin)/dfft.delta_p) + 0.5;
        Tkmax = cmath.phase(ff[kmax]);
        backmax = math.cos(Tkmax+(2*math.pi*kmax*kbeam/(2*ff.size()-1)) );
        ### Here it should be possible to calculate a gradient.
        ### Then minimize with respect to two coordinates.  Use lbfgs?  Have second derivatives?
        ### can I do something local to model the cosine wave?
        ### direction of wave travel.  Period. phase.
        sum_score += backmax;
      #if t == unique:
      #  print t, kmax, dfft.pmin, dfft.delta_p, Tkmax,(2*math.pi*kmax*kbeam/(2*ff.size()-1))
    return sum_score

  def get_S0_vector_score(self,trial_beam,unique):
    trial_beam = matrix.col(trial_beam)
    reciprocal_space_vectors = self.raw_spot_positions_mm_to_reciprocal_space(
      self.raw_spot_input, self.detector, self.inv_wave, trial_beam, self.axis,
      self.panelID)

    return self.sum_score_detail(reciprocal_space_vectors)

  def optimize_S0_local_scope(self):
      """Local scope: find the optimal S0 vector closest to the input S0 vector
         (local minimum, simple minimization)"""

      ############  Implement a direct beam check right here #########################
      unique=0
      # construct two vectors that are perpendicular to the beam.  Gives a basis for refining beam
      beamr0 = self.S0_vector.cross(self.axis).normalize()
      beamr1 = beamr0.cross(self.S0_vector).normalize()
      beamr2 = beamr1.cross(self.S0_vector).normalize()

      assert approx_equal(self.S0_vector.dot(beamr1), 0.)
      assert approx_equal(self.S0_vector.dot(beamr2), 0.)
      assert approx_equal(beamr2.dot(beamr1), 0.)
      # so the orthonormal vectors are self.S0_vector, beamr1 and beamr2

      grid = 10

      # DO A SIMPLEX MINIMIZATION
      from scitbx.simplex import simplex_opt
      class test_simplex_method(object):
        def __init__(selfOO):
          selfOO.starting_simplex=[]
          selfOO.n = 2
          for ii in range(selfOO.n+1):
            selfOO.starting_simplex.append(flex.random_double(selfOO.n))
          selfOO.optimizer = simplex_opt( dimension=selfOO.n,
                                        matrix  = selfOO.starting_simplex,
                                        evaluator = selfOO,
                                        tolerance=1e-7)
          selfOO.x = selfOO.optimizer.get_solution()

        def target(selfOO, vector):
          newvec = matrix.col(self.S0_vector) + vector[0]*0.0002*beamr1 + vector[1]*0.0002*beamr2
          normal = newvec.normalize() * self.inv_wave
          return -self.get_S0_vector_score(normal,unique) # extended API

      MIN = test_simplex_method()
      #MIN = test_cma_es()
      print "MINIMUM=",list(MIN.x)
      newvec = matrix.col(self.S0_vector) + MIN.x[0]*0.0002*beamr1 + MIN.x[1]*0.0002*beamr2
      new_S0_vector = newvec.normalize() * self.inv_wave

      print "old S0:",list(self.S0_vector.elems)
      print "new S0",list(new_S0_vector.elems)

      plot = False
      if plot:
        scores = flex.double()
        for x in xrange(-grid,grid+1):
         for y in xrange(-grid,grid+1):
          ref = matrix.col(self.S0_vector)
          newvec = ref + x*0.0002*beamr1 + y*0.0002*beamr2
          normal = newvec.normalize() * self.inv_wave
          scores.append( self.get_S0_vector_score(normal,unique) ) # extended API

        def show_plot(grid,excursi):
          excursi.reshape(flex.grid(grid, grid))

          from matplotlib import pyplot as plt
          plt.figure()
          CS = plt.contour([i*0.2 for i in xrange(grid)],[i*0.2 for i in xrange(grid)], excursi.as_numpy_array())
          plt.clabel(CS, inline=1, fontsize=10, fmt="%6.3f")
          plt.title("Score as to beam likelihood")
          plt.scatter([0.1*(grid-1)],[0.1*(grid-1)],color='g',marker='o')
          plt.scatter([0.1*(grid-1)+0.2*MIN.x[0]] , [0.1*(grid-1)+0.2*MIN.x[1]],color='r',marker='*')
          plt.axes().set_aspect("equal")
          plt.show()

        show_plot(2 * grid + 1, scores)

      return new_S0_vector

  @staticmethod
  def get_new_detector(old_detector,origin_offset):
    import copy
    new_panels = []
    for panel in old_detector:
      new_panel = copy.deepcopy(panel)
      new_panel.set_frame(fast_axis=panel.get_fast_axis(),
                          slow_axis=panel.get_slow_axis(),
                          origin=matrix.col(panel.get_origin()) + origin_offset)
      new_panels.append(new_panel)
    return new_panels

  def get_origin_offset_score(self,trial_origin_offset):
    trial_detector = dps_extended.get_new_detector(self.detector,trial_origin_offset)
    reciprocal_space_vectors = self.raw_spot_positions_mm_to_reciprocal_space(
      self.raw_spot_input, trial_detector, self.inv_wave, self.S0_vector, self.axis,
      self.panelID)

    return self.sum_score_detail(reciprocal_space_vectors)

  def optimize_origin_offset_local_scope(self):
      """Local scope: find the optimal origin-offset closest to the current overall detector position
         (local minimum, simple minimization)"""
      # construct two vectors that are perpendicular to the beam.  Gives a basis for refining beam
      beamr0 = self.S0_vector.cross(self.axis).normalize()
      beamr1 = beamr0.cross(self.S0_vector).normalize()
      beamr2 = beamr1.cross(self.S0_vector).normalize()

      assert approx_equal(self.S0_vector.dot(beamr1), 0.)
      assert approx_equal(self.S0_vector.dot(beamr2), 0.)
      assert approx_equal(beamr2.dot(beamr1), 0.)
      # so the orthonormal vectors are self.S0_vector, beamr1 and beamr2

      grid = 10

      # DO A SIMPLEX MINIMIZATION
      from scitbx.simplex import simplex_opt
      class test_simplex_method(object):
        def __init__(selfOO):
          selfOO.starting_simplex=[]
          selfOO.n = 2
          for ii in range(selfOO.n+1):
            selfOO.starting_simplex.append(flex.random_double(selfOO.n))
          selfOO.optimizer = simplex_opt( dimension=selfOO.n,
                                        matrix  = selfOO.starting_simplex,
                                        evaluator = selfOO,
                                        tolerance=1e-7)
          selfOO.x = selfOO.optimizer.get_solution()

        def target(selfOO, vector):
          trial_origin_offset = vector[0]*0.2*beamr1 + vector[1]*0.2*beamr2
          return -self.get_origin_offset_score(trial_origin_offset)

      MIN = test_simplex_method()
      trial_origin_offset =  MIN.x[0]*0.2*beamr1 + MIN.x[1]*0.2*beamr2

      print "new origin_offset",list(trial_origin_offset.elems)

      plot = False
      if plot:
        scores = flex.double()
        for x in xrange(-grid,grid+1):
         for y in xrange(-grid,grid+1):
          new_origin_offset = x*0.2*beamr1 + y*0.2*beamr2
          scores.append( self.get_origin_offset_score(new_origin_offset) )

        def show_plot(grid,excursi):
          excursi.reshape(flex.grid(grid, grid))

          from matplotlib import pyplot as plt
          plt.figure()
          CS = plt.contour([i*0.2 for i in xrange(grid)],[i*0.2 for i in xrange(grid)], excursi.as_numpy_array())
          plt.clabel(CS, inline=1, fontsize=10, fmt="%6.3f")
          plt.title("Score as to beam likelihood")
          plt.scatter([0.1*(grid-1)],[0.1*(grid-1)],color='g',marker='o')
          plt.scatter([0.1*(grid-1)+0.2*MIN.x[0]] , [0.1*(grid-1)+0.2*MIN.x[1]],color='r',marker='*')
          plt.axes().set_aspect("equal")
          plt.show()

        show_plot(2 * grid + 1, scores)

      return dps_extended.get_new_detector(self.detector,trial_origin_offset)

  def get_basis_general(self):
    """side-effect: sets orientation matrix"""
    from rstbx.indexing_api.basis_choice import SelectBasisMetaprocedure as SBM
    pd = {}
    M = SBM(input_index_engine = self,input_dictionary = pd, horizon_phil = self.horizon_phil) # extended API

    print "Finished SELECT BASIS with solution M",M

    from rstbx.dps_core.lepage import iotbx_converter
    L = iotbx_converter(self.getOrientation().unit_cell().minimum_cell(),5.0) # extended API
    supergroup = L[0]

    triclinic = self.getOrientation().unit_cell() # extended API

    cb_op = supergroup['cb_op_inp_best'].c().as_double_array()[0:9]
    orient = self.getOrientation() # extended API
    orient_best = orient.change_basis(matrix.sqr(cb_op).transpose())
    constrain_orient = orient_best.constrain(supergroup['system'])
    self.setOrientation(constrain_orient) # extended API

    if True:
      for subgroup in L:
        print subgroup.short_digest()
      print "\ntriclinic cell=%s volume(A^3)=%.3f"%(triclinic,triclinic.volume())
      print "\nafter symmetrizing to %s:"%supergroup.reference_lookup_symbol()
      #M.show_rms()
    return L

class DPS_primitive_lattice(dps_extended):
  def __init__(self, max_cell, recommended_grid_sampling_rad, horizon_phil):
    from libtbx import adopt_init_args
    adopt_init_args(self,locals())
    dps_extended.__init__(self)
    self.OK_to_reset_saga_spot_status = True
