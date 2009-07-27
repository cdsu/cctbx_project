#ifndef SCITBX_RIGID_BODY_BODY_LIB_H
#define SCITBX_RIGID_BODY_BODY_LIB_H

#include <scitbx/rigid_body/body_t.h>
#include <scitbx/rigid_body/joint_lib.h>
#include <scitbx/rigid_body/spatial_lib.h>
#include <scitbx/math/inertia_tensor.h>

namespace scitbx { namespace rigid_body { namespace body_lib {

  template <typename FloatType>
  struct mass_points_cache
  {
    typedef FloatType ft;

    af::const_ref<vec3<ft> > sites;
    af::const_ref<ft> masses;
    protected:
      mutable boost::optional<ft> sum_of_masses_;
      mutable boost::optional<vec3<ft> > center_of_mass_;
    public:

    mass_points_cache() {}

    mass_points_cache(
      af::const_ref<vec3<ft> > const& sites_,
      af::const_ref<ft> const& masses_)
    {
      SCITBX_ASSERT(masses.size() == sites.size());
    }

    ft const&
    sum_of_masses() const
    {
      if (!sum_of_masses_) {
        sum_of_masses_ = boost::optional<ft>(af::sum(masses));
      }
      return *sum_of_masses_;
    }

    vec3<ft> const&
    center_of_mass() const
    {
      if (!center_of_mass_) {
        SCITBX_ASSERT(masses.size() != 0);
        SCITBX_ASSERT(sum_of_masses() != 0);
        SCITBX_ASSERT(masses.size() == sites.size());
        vec3<ft> sms(0,0,0);
        unsigned n = boost::numeric_cast<unsigned>(masses.size());
        for(unsigned i=0;i<n;i++) {
          sms += masses[i] * sites[i];
        }
        center_of_mass_ = boost::optional<vec3<ft> >(sms / sum_of_masses());
      }
      return *center_of_mass_;
    }

    sym_mat3<ft>
    inertia(
      vec3<ft> const& pivot) const
    {
      return math::inertia_tensor(sites, masses, pivot);
    }

    af::versa<ft, af::mat_grid>
    spatial_inertia() const
    {
      center_of_mass();
      return spatial_lib::mci(
        *sum_of_masses_,
        *center_of_mass_,
        inertia(*center_of_mass_));
    }

    af::versa<ft, af::mat_grid>
    spatial_inertia(
      rotr3<ft> const& alignment_cb_0b) const
    {
      center_of_mass();
      return spatial_lib::mci(
        *sum_of_masses_,
        alignment_cb_0b * (*center_of_mass_),
        inertia(*center_of_mass_).tensor_transform(alignment_cb_0b.r));
    }
  };

  template <typename FloatType=double>
  struct zero_dof : body_t<FloatType>
  {
    typedef FloatType ft;

    af::const_ref<ft> qd_;

    zero_dof() {}

    zero_dof(
      af::const_ref<vec3<ft> > const& sites,
      af::const_ref<ft> const& masses)
    {
      SCITBX_ASSERT(masses.size() == sites.size());
      this->number_of_sites = boost::numeric_cast<unsigned>(sites.size());
      this->sum_of_masses = af::sum(masses);
      this->alignment = shared_ptr<alignment_t<ft> >(
        new joint_lib::zero_dof_alignment<ft>());
      this->i_spatial = af::versa<ft, af::mat_grid>(af::mat_grid(6,6), 0);
      this->joint = shared_ptr<joint_t<ft> >(
        new joint_lib::zero_dof<ft>());
      qd_ = af::const_ref<ft>(0, 0);
    }

    virtual
    af::const_ref<ft>
    qd() const { return qd_; }
  };

  template <typename FloatType=double>
  struct six_dof : body_t<FloatType>
  {
    typedef FloatType ft;

    af::tiny<ft, 7> qd_;

    six_dof() {}

    six_dof(
      af::const_ref<vec3<ft> > const& sites,
      af::const_ref<ft> const& masses)
    {
      this->number_of_sites = boost::numeric_cast<unsigned>(sites.size());
      mass_points_cache<ft> mp(sites, masses);
      this->sum_of_masses = mp.sum_of_masses();
      this->alignment = shared_ptr<alignment_t<ft> >(
        new joint_lib::six_dof_alignment<ft>(mp.center_of_mass()));
      this->i_spatial = mp.spatial_inertia(this->alignment->cb_0b);
      this->joint = shared_ptr<joint_t<ft> >(
        new joint_lib::six_dof<ft>(
          af::tiny<ft, 4>(1,0,0,0),
          vec3<ft>(0,0,0)));
      af::const_ref<ft> qd0 = this->joint->qd_zero();
      std::copy(qd0.begin(), qd0.end(), qd_.begin());
    }

    virtual
    af::const_ref<ft>
    qd() const { return qd_.const_ref(); }
  };

  template <typename FloatType=double>
  struct spherical : body_t<FloatType>
  {
    typedef FloatType ft;

    af::tiny<ft, 3> qd_;

    spherical() {}

    spherical(
      af::const_ref<vec3<ft> > const& sites,
      af::const_ref<ft> const& masses,
      vec3<ft> const& pivot)
    {
      this->number_of_sites = boost::numeric_cast<unsigned>(sites.size());
      mass_points_cache<ft> mp(sites, masses);
      this->sum_of_masses = mp.sum_of_masses();
      this->alignment = shared_ptr<alignment_t<ft> >(
        new joint_lib::spherical_alignment<ft>(pivot));
      this->i_spatial = mp.spatial_inertia(this->alignment->cb_0b);
      this->joint = shared_ptr<joint_t<ft> >(
        new joint_lib::spherical<ft>(
          af::tiny<ft, 4>(1,0,0,0)));
      af::const_ref<ft> qd0 = this->joint->qd_zero();
      std::copy(qd0.begin(), qd0.end(), qd_.begin());
    }

    virtual
    af::const_ref<ft>
    qd() const { return qd_.const_ref(); }
  };

  template <typename FloatType=double>
  struct revolute : body_t<FloatType>
  {
    typedef FloatType ft;

    ft qd_;

    revolute() {}

    revolute(
      af::const_ref<vec3<ft> > const& sites,
      af::const_ref<ft> const& masses,
      vec3<ft> const& pivot,
      vec3<ft> const& normal)
    {
      this->number_of_sites = boost::numeric_cast<unsigned>(sites.size());
      mass_points_cache<ft> mp(sites, masses);
      this->sum_of_masses = mp.sum_of_masses();
      this->alignment = shared_ptr<alignment_t<ft> >(
        new joint_lib::revolute_alignment<ft>(pivot, normal));
      this->i_spatial = mp.spatial_inertia(this->alignment->cb_0b);
      this->joint = shared_ptr<joint_t<ft> >(
        new joint_lib::revolute<ft>(af::tiny<ft, 1>(qd_)));
      qd_ = this->joint->qd_zero()[0];
    }

    virtual
    af::const_ref<ft>
    qd() const { return af::const_ref<ft>(&qd_, 1); }
  };

  template <typename FloatType=double>
  struct translational : body_t<FloatType>
  {
    typedef FloatType ft;

    af::tiny<ft, 3> qd_;

    translational() {}

    translational(
      af::const_ref<vec3<ft> > const& sites,
      af::const_ref<ft> const& masses)
    {
      this->number_of_sites = boost::numeric_cast<unsigned>(sites.size());
      mass_points_cache<ft> mp(sites, masses);
      this->sum_of_masses = mp.sum_of_masses();
      this->alignment = shared_ptr<alignment_t<ft> >(
        new joint_lib::translational_alignment<ft>(mp.center_of_mass()));
      this->i_spatial = mp.spatial_inertia(this->alignment->cb_0b);
      this->joint = shared_ptr<joint_t<ft> >(
        new joint_lib::translational<ft>(
          vec3<ft>(0,0,0)));
      af::const_ref<ft> qd0 = this->joint->qd_zero();
      std::copy(qd0.begin(), qd0.end(), qd_.begin());
    }

    virtual
    af::const_ref<ft>
    qd() const { return qd_.const_ref(); }
  };

}}} // namespace scitbx::rigid_body::body_lib

#endif // GUARD
