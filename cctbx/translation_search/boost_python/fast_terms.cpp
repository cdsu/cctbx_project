#include <cctbx/boost_python/flex_fwd.h>

#include <cctbx/translation_search/fast_terms.h>
#include <boost/python/class.hpp>
#include <boost/python/args.hpp>
#include <boost/python/return_internal_reference.hpp>

namespace cctbx { namespace translation_search { namespace boost_python {

namespace {

  struct fast_terms_wrappers
  {
    typedef fast_terms<> w_t;

    static void
    wrap()
    {
      using namespace boost::python;
      typedef return_internal_reference<> rir;
      class_<w_t>("fast_terms", no_init)
        .def(init<af::int3 const&,
                  bool,
                  af::const_ref<miller::index<> > const&,
                  af::const_ref<std::complex<double> > >(
          (arg("gridding"),
           arg("anomalous_flag"),
           arg("miller_indices_p1_f_calc"),
           arg("p1_f_calc"))))
        .def("summation", &w_t::summation, rir(),
          (arg("space_group"),
           arg("miller_indices_f_obs"),
           arg("m"),
           arg("f_part"),
           arg("squared_flag")))
        .def("fft", &w_t::fft, rir())
        .def("accu_real_copy", &w_t::accu_real_copy)
      ;
    }
  };

} // namespace <anoymous>

  void wrap_fast_terms()
  {
    fast_terms_wrappers::wrap();
  }

}}} // namespace cctbx::translation_search::boost_python
