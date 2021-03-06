/*
 * Generated by gdbus-codegen 2.48.1. DO NOT EDIT.
 *
 * The license of this code is the same as for the source it was derived from.
 */

#ifndef __TCMUHANDLER_GENERATED_H__
#define __TCMUHANDLER_GENERATED_H__

#include <gio/gio.h>

G_BEGIN_DECLS


/* ------------------------------------------------------------------------ */
/* Declarations for org.kernel.TCMUService1 */

#define TYPE_TCMUSERVICE1 (tcmuservice1_get_type ())
#define TCMUSERVICE1(o) (G_TYPE_CHECK_INSTANCE_CAST ((o), TYPE_TCMUSERVICE1, TCMUService1))
#define IS_TCMUSERVICE1(o) (G_TYPE_CHECK_INSTANCE_TYPE ((o), TYPE_TCMUSERVICE1))
#define TCMUSERVICE1_GET_IFACE(o) (G_TYPE_INSTANCE_GET_INTERFACE ((o), TYPE_TCMUSERVICE1, TCMUService1Iface))

struct _TCMUService1;
typedef struct _TCMUService1 TCMUService1;
typedef struct _TCMUService1Iface TCMUService1Iface;

struct _TCMUService1Iface
{
  GTypeInterface parent_iface;


  gboolean (*handle_check_config) (
    TCMUService1 *object,
    GDBusMethodInvocation *invocation,
    const gchar *arg_configstr);

  const gchar * (*get_config_desc) (TCMUService1 *object);

};

GType tcmuservice1_get_type (void) G_GNUC_CONST;

GDBusInterfaceInfo *tcmuservice1_interface_info (void);
guint tcmuservice1_override_properties (GObjectClass *klass, guint property_id_begin);


/* D-Bus method call completion functions: */
void tcmuservice1_complete_check_config (
    TCMUService1 *object,
    GDBusMethodInvocation *invocation,
    gboolean is_valid,
    const gchar *message);



/* D-Bus method calls: */
void tcmuservice1_call_check_config (
    TCMUService1 *proxy,
    const gchar *arg_configstr,
    GCancellable *cancellable,
    GAsyncReadyCallback callback,
    gpointer user_data);

gboolean tcmuservice1_call_check_config_finish (
    TCMUService1 *proxy,
    gboolean *out_is_valid,
    gchar **out_message,
    GAsyncResult *res,
    GError **error);

gboolean tcmuservice1_call_check_config_sync (
    TCMUService1 *proxy,
    const gchar *arg_configstr,
    gboolean *out_is_valid,
    gchar **out_message,
    GCancellable *cancellable,
    GError **error);



/* D-Bus property accessors: */
const gchar *tcmuservice1_get_config_desc (TCMUService1 *object);
gchar *tcmuservice1_dup_config_desc (TCMUService1 *object);
void tcmuservice1_set_config_desc (TCMUService1 *object, const gchar *value);


/* ---- */

#define TYPE_TCMUSERVICE1_PROXY (tcmuservice1_proxy_get_type ())
#define TCMUSERVICE1_PROXY(o) (G_TYPE_CHECK_INSTANCE_CAST ((o), TYPE_TCMUSERVICE1_PROXY, TCMUService1Proxy))
#define TCMUSERVICE1_PROXY_CLASS(k) (G_TYPE_CHECK_CLASS_CAST ((k), TYPE_TCMUSERVICE1_PROXY, TCMUService1ProxyClass))
#define TCMUSERVICE1_PROXY_GET_CLASS(o) (G_TYPE_INSTANCE_GET_CLASS ((o), TYPE_TCMUSERVICE1_PROXY, TCMUService1ProxyClass))
#define IS_TCMUSERVICE1_PROXY(o) (G_TYPE_CHECK_INSTANCE_TYPE ((o), TYPE_TCMUSERVICE1_PROXY))
#define IS_TCMUSERVICE1_PROXY_CLASS(k) (G_TYPE_CHECK_CLASS_TYPE ((k), TYPE_TCMUSERVICE1_PROXY))

typedef struct _TCMUService1Proxy TCMUService1Proxy;
typedef struct _TCMUService1ProxyClass TCMUService1ProxyClass;
typedef struct _TCMUService1ProxyPrivate TCMUService1ProxyPrivate;

struct _TCMUService1Proxy
{
  /*< private >*/
  GDBusProxy parent_instance;
  TCMUService1ProxyPrivate *priv;
};

struct _TCMUService1ProxyClass
{
  GDBusProxyClass parent_class;
};

GType tcmuservice1_proxy_get_type (void) G_GNUC_CONST;

#if GLIB_CHECK_VERSION(2, 44, 0)
G_DEFINE_AUTOPTR_CLEANUP_FUNC (TCMUService1Proxy, g_object_unref)
#endif

void tcmuservice1_proxy_new (
    GDBusConnection     *connection,
    GDBusProxyFlags      flags,
    const gchar         *name,
    const gchar         *object_path,
    GCancellable        *cancellable,
    GAsyncReadyCallback  callback,
    gpointer             user_data);
TCMUService1 *tcmuservice1_proxy_new_finish (
    GAsyncResult        *res,
    GError             **error);
TCMUService1 *tcmuservice1_proxy_new_sync (
    GDBusConnection     *connection,
    GDBusProxyFlags      flags,
    const gchar         *name,
    const gchar         *object_path,
    GCancellable        *cancellable,
    GError             **error);

void tcmuservice1_proxy_new_for_bus (
    GBusType             bus_type,
    GDBusProxyFlags      flags,
    const gchar         *name,
    const gchar         *object_path,
    GCancellable        *cancellable,
    GAsyncReadyCallback  callback,
    gpointer             user_data);
TCMUService1 *tcmuservice1_proxy_new_for_bus_finish (
    GAsyncResult        *res,
    GError             **error);
TCMUService1 *tcmuservice1_proxy_new_for_bus_sync (
    GBusType             bus_type,
    GDBusProxyFlags      flags,
    const gchar         *name,
    const gchar         *object_path,
    GCancellable        *cancellable,
    GError             **error);


/* ---- */

#define TYPE_TCMUSERVICE1_SKELETON (tcmuservice1_skeleton_get_type ())
#define TCMUSERVICE1_SKELETON(o) (G_TYPE_CHECK_INSTANCE_CAST ((o), TYPE_TCMUSERVICE1_SKELETON, TCMUService1Skeleton))
#define TCMUSERVICE1_SKELETON_CLASS(k) (G_TYPE_CHECK_CLASS_CAST ((k), TYPE_TCMUSERVICE1_SKELETON, TCMUService1SkeletonClass))
#define TCMUSERVICE1_SKELETON_GET_CLASS(o) (G_TYPE_INSTANCE_GET_CLASS ((o), TYPE_TCMUSERVICE1_SKELETON, TCMUService1SkeletonClass))
#define IS_TCMUSERVICE1_SKELETON(o) (G_TYPE_CHECK_INSTANCE_TYPE ((o), TYPE_TCMUSERVICE1_SKELETON))
#define IS_TCMUSERVICE1_SKELETON_CLASS(k) (G_TYPE_CHECK_CLASS_TYPE ((k), TYPE_TCMUSERVICE1_SKELETON))

typedef struct _TCMUService1Skeleton TCMUService1Skeleton;
typedef struct _TCMUService1SkeletonClass TCMUService1SkeletonClass;
typedef struct _TCMUService1SkeletonPrivate TCMUService1SkeletonPrivate;

struct _TCMUService1Skeleton
{
  /*< private >*/
  GDBusInterfaceSkeleton parent_instance;
  TCMUService1SkeletonPrivate *priv;
};

struct _TCMUService1SkeletonClass
{
  GDBusInterfaceSkeletonClass parent_class;
};

GType tcmuservice1_skeleton_get_type (void) G_GNUC_CONST;

#if GLIB_CHECK_VERSION(2, 44, 0)
G_DEFINE_AUTOPTR_CLEANUP_FUNC (TCMUService1Skeleton, g_object_unref)
#endif

TCMUService1 *tcmuservice1_skeleton_new (void);


/* ---- */

#define TYPE_OBJECT (object_get_type ())
#define OBJECT(o) (G_TYPE_CHECK_INSTANCE_CAST ((o), TYPE_OBJECT, Object))
#define IS_OBJECT(o) (G_TYPE_CHECK_INSTANCE_TYPE ((o), TYPE_OBJECT))
#define OBJECT_GET_IFACE(o) (G_TYPE_INSTANCE_GET_INTERFACE ((o), TYPE_OBJECT, Object))

struct _Object;
typedef struct _Object Object;
typedef struct _ObjectIface ObjectIface;

struct _ObjectIface
{
  GTypeInterface parent_iface;
};

GType object_get_type (void) G_GNUC_CONST;

TCMUService1 *object_get_tcmuservice1 (Object *object);
TCMUService1 *object_peek_tcmuservice1 (Object *object);

#define TYPE_OBJECT_PROXY (object_proxy_get_type ())
#define OBJECT_PROXY(o) (G_TYPE_CHECK_INSTANCE_CAST ((o), TYPE_OBJECT_PROXY, ObjectProxy))
#define OBJECT_PROXY_CLASS(k) (G_TYPE_CHECK_CLASS_CAST ((k), TYPE_OBJECT_PROXY, ObjectProxyClass))
#define OBJECT_PROXY_GET_CLASS(o) (G_TYPE_INSTANCE_GET_CLASS ((o), TYPE_OBJECT_PROXY, ObjectProxyClass))
#define IS_OBJECT_PROXY(o) (G_TYPE_CHECK_INSTANCE_TYPE ((o), TYPE_OBJECT_PROXY))
#define IS_OBJECT_PROXY_CLASS(k) (G_TYPE_CHECK_CLASS_TYPE ((k), TYPE_OBJECT_PROXY))

typedef struct _ObjectProxy ObjectProxy;
typedef struct _ObjectProxyClass ObjectProxyClass;
typedef struct _ObjectProxyPrivate ObjectProxyPrivate;

struct _ObjectProxy
{
  /*< private >*/
  GDBusObjectProxy parent_instance;
  ObjectProxyPrivate *priv;
};

struct _ObjectProxyClass
{
  GDBusObjectProxyClass parent_class;
};

GType object_proxy_get_type (void) G_GNUC_CONST;

#if GLIB_CHECK_VERSION(2, 44, 0)
G_DEFINE_AUTOPTR_CLEANUP_FUNC (ObjectProxy, g_object_unref)
#endif

ObjectProxy *object_proxy_new (GDBusConnection *connection, const gchar *object_path);

#define TYPE_OBJECT_SKELETON (object_skeleton_get_type ())
#define OBJECT_SKELETON(o) (G_TYPE_CHECK_INSTANCE_CAST ((o), TYPE_OBJECT_SKELETON, ObjectSkeleton))
#define OBJECT_SKELETON_CLASS(k) (G_TYPE_CHECK_CLASS_CAST ((k), TYPE_OBJECT_SKELETON, ObjectSkeletonClass))
#define OBJECT_SKELETON_GET_CLASS(o) (G_TYPE_INSTANCE_GET_CLASS ((o), TYPE_OBJECT_SKELETON, ObjectSkeletonClass))
#define IS_OBJECT_SKELETON(o) (G_TYPE_CHECK_INSTANCE_TYPE ((o), TYPE_OBJECT_SKELETON))
#define IS_OBJECT_SKELETON_CLASS(k) (G_TYPE_CHECK_CLASS_TYPE ((k), TYPE_OBJECT_SKELETON))

typedef struct _ObjectSkeleton ObjectSkeleton;
typedef struct _ObjectSkeletonClass ObjectSkeletonClass;
typedef struct _ObjectSkeletonPrivate ObjectSkeletonPrivate;

struct _ObjectSkeleton
{
  /*< private >*/
  GDBusObjectSkeleton parent_instance;
  ObjectSkeletonPrivate *priv;
};

struct _ObjectSkeletonClass
{
  GDBusObjectSkeletonClass parent_class;
};

GType object_skeleton_get_type (void) G_GNUC_CONST;

#if GLIB_CHECK_VERSION(2, 44, 0)
G_DEFINE_AUTOPTR_CLEANUP_FUNC (ObjectSkeleton, g_object_unref)
#endif

ObjectSkeleton *object_skeleton_new (const gchar *object_path);
void object_skeleton_set_tcmuservice1 (ObjectSkeleton *object, TCMUService1 *interface_);

/* ---- */

#define TYPE_OBJECT_MANAGER_CLIENT (object_manager_client_get_type ())
#define OBJECT_MANAGER_CLIENT(o) (G_TYPE_CHECK_INSTANCE_CAST ((o), TYPE_OBJECT_MANAGER_CLIENT, ObjectManagerClient))
#define OBJECT_MANAGER_CLIENT_CLASS(k) (G_TYPE_CHECK_CLASS_CAST ((k), TYPE_OBJECT_MANAGER_CLIENT, ObjectManagerClientClass))
#define OBJECT_MANAGER_CLIENT_GET_CLASS(o) (G_TYPE_INSTANCE_GET_CLASS ((o), TYPE_OBJECT_MANAGER_CLIENT, ObjectManagerClientClass))
#define IS_OBJECT_MANAGER_CLIENT(o) (G_TYPE_CHECK_INSTANCE_TYPE ((o), TYPE_OBJECT_MANAGER_CLIENT))
#define IS_OBJECT_MANAGER_CLIENT_CLASS(k) (G_TYPE_CHECK_CLASS_TYPE ((k), TYPE_OBJECT_MANAGER_CLIENT))

typedef struct _ObjectManagerClient ObjectManagerClient;
typedef struct _ObjectManagerClientClass ObjectManagerClientClass;
typedef struct _ObjectManagerClientPrivate ObjectManagerClientPrivate;

struct _ObjectManagerClient
{
  /*< private >*/
  GDBusObjectManagerClient parent_instance;
  ObjectManagerClientPrivate *priv;
};

struct _ObjectManagerClientClass
{
  GDBusObjectManagerClientClass parent_class;
};

#if GLIB_CHECK_VERSION(2, 44, 0)
G_DEFINE_AUTOPTR_CLEANUP_FUNC (ObjectManagerClient, g_object_unref)
#endif

GType object_manager_client_get_type (void) G_GNUC_CONST;

GType object_manager_client_get_proxy_type (GDBusObjectManagerClient *manager, const gchar *object_path, const gchar *interface_name, gpointer user_data);

void object_manager_client_new (
    GDBusConnection        *connection,
    GDBusObjectManagerClientFlags  flags,
    const gchar            *name,
    const gchar            *object_path,
    GCancellable           *cancellable,
    GAsyncReadyCallback     callback,
    gpointer                user_data);
GDBusObjectManager *object_manager_client_new_finish (
    GAsyncResult        *res,
    GError             **error);
GDBusObjectManager *object_manager_client_new_sync (
    GDBusConnection        *connection,
    GDBusObjectManagerClientFlags  flags,
    const gchar            *name,
    const gchar            *object_path,
    GCancellable           *cancellable,
    GError                **error);

void object_manager_client_new_for_bus (
    GBusType                bus_type,
    GDBusObjectManagerClientFlags  flags,
    const gchar            *name,
    const gchar            *object_path,
    GCancellable           *cancellable,
    GAsyncReadyCallback     callback,
    gpointer                user_data);
GDBusObjectManager *object_manager_client_new_for_bus_finish (
    GAsyncResult        *res,
    GError             **error);
GDBusObjectManager *object_manager_client_new_for_bus_sync (
    GBusType                bus_type,
    GDBusObjectManagerClientFlags  flags,
    const gchar            *name,
    const gchar            *object_path,
    GCancellable           *cancellable,
    GError                **error);


G_END_DECLS

#endif /* __TCMUHANDLER_GENERATED_H__ */
