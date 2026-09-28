#include "my_application.h"

struct _MyApplication {
  GtkApplication parent_instance;
};

G_DEFINE_TYPE(MyApplication, my_application, GTK_TYPE_APPLICATION)
